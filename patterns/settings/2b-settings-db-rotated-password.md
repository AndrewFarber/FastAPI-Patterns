---
title: "Rotated DB passwords"
category: persistence
tags: [settings, database, secrets-rotation, secrets-manager]
status: draft
related: ["[[2b-settings-db]]", "[[4a-settings-refreshing-values-cache]]", "[[1e-settings-lambda]]"]
---

# Rotated DB passwords

## Problem
With Secrets Manager rotation, the DB password changes under a running app. A password read once at startup (or put into a Lambda env var at deploy time) works until the next rotation; after that, every new connection fails until the execution environment is replaced.

## Use when
- The DB password lives in Secrets Manager with rotation enabled (AWS setup below).

## Avoid when
- The app uses IAM authentication ([[2b-settings-db-iam-auth]]): tokens are generated per connection, so there is nothing to rotate.
- The password never rotates: use `PasswordAuth` ([[2b-settings-db]]).

## Solution
`RotatedSecretAuth` has its own module and is part of the `DbAuth` union in `app/config/db.py` ([[2b-settings-db]]):

```python
# app/config/db_rotated.py
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RotatedSecretAuth(BaseModel):
    """A password rotated by Secrets Manager, read per new connection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["rotated_secret"]
    secret_id: str                                  # the secret's ARN (a name works too)
    region: str
    ttl_seconds: float = Field(default=300, gt=0)   # how long to cache the secret
```

Fetch the current password per *new* connection through SQLAlchemy's `do_connect` event, using the cache from [[4a-settings-refreshing-values-cache]]. Pooled connections stay open; only new ones need the new password.

```python
# app/db/rotated_password.py
import json

import psycopg
from sqlalchemy import Engine, event

from app.clients.aws_values import secrets_manager_cache
from app.config.db import DbSettings
from app.config.db_rotated import RotatedSecretAuth


def add_rotated_password(engine: Engine, db: DbSettings) -> None:
    """Use the current Secrets Manager password for each new connection."""
    assert isinstance(db.auth, RotatedSecretAuth)
    auth = db.auth
    secrets = secrets_manager_cache(auth.region, auth.ttl_seconds)

    @event.listens_for(engine, "do_connect")
    def connect_with_current_password(dialect, conn_rec, cargs, cparams):
        secret = json.loads(secrets.get(auth.secret_id))       # {"username": ..., "password": ...}
        cparams["user"] = secret["username"]
        cparams["password"] = secret["password"]
        try:
            return dialect.connect(*cargs, **cparams)
        except psycopg.OperationalError:
            # The password may have just rotated. libpq gives connection errors no SQLSTATE,
            # so retry only if Secrets Manager now has a different secret: a DB outage fails once.
            secrets.invalidate(auth.secret_id)
            fresh = json.loads(secrets.get(auth.secret_id))
            if fresh == secret:
                raise
        cparams["user"] = fresh["username"]
        cparams["password"] = fresh["password"]
        return dialect.connect(*cargs, **cparams)
```

`build_engine()` ([[2b-settings-db]]) calls `add_rotated_password()` when `db.auth` is a `RotatedSecretAuth`.

```bash
DB__AUTH__METHOD=rotated_secret
DB__AUTH__SECRET_ID=arn:aws:secretsmanager:us-east-1:123456789012:secret:orders/prd/db-app-AbCdEf
DB__AUTH__REGION=us-east-1
```

- **Retry once, only with a different secret.** Between a rotation and the cache expiring, the cached password is wrong; the failed connection invalidates it and refetches. libpq reports no SQLSTATE for connection failures, so an auth error looks like an outage. Retrying only when the secret changed keeps an outage to one connect timeout instead of two.
- **Use `username` from the secret too.** Alternating-users rotation switches between two users (`orders_app` and `orders_app_clone`), so the username changes as well.
- **`DB__USER` is still required** by `DbSettings`; set it to the app user. The secret's username replaces it on each connection.

### On Lambda
- **Grant read, pass the ARN.** The function's env vars carry only the secret's ARN in `DB__AUTH__SECRET_ID`, and its role may call `secretsmanager:GetSecretValue` on that secret. The password never appears in the function configuration.
- **The cache lives per execution environment** ([[1e-settings-lambda]]). Each new environment fetches the secret on its first connection; with a pool of one, that is usually the only fetch until the TTL expires.
- **Alternatives to the cache:** the AWS Parameters and Secrets Lambda Extension (`localhost:2773`, added to the image like any extension) or Powertools' `parameters.get_secret(..., max_age=...)`. The retry on a failed connection is still needed.
- **Behind RDS Proxy** the proxy reads the secret itself; authenticating to it with IAM removes this hook ([[2b-settings-db-rds-tls]]).

### AWS setup
- **Two secrets.** The master user's, rotated with the single-user strategy and used only by administrators and the rotation function. The app user's, rotated with the alternating-users strategy and read by the app. Never give the app the master secret.
- **The app user exists first.** Create `orders_app` with its grants (e.g. in a migration) before the first rotation: alternating-users rotation clones an existing user. Its secret holds `masterarn`, the master secret that rotation uses to change passwords.
- **Behind RDS Proxy, rotate single-user.** The proxy doesn't support the alternating-users strategy, so secrets it reads use single-user rotation ([[2b-settings-db-rds-tls]]).
- **The rotation function needs a route to Secrets Manager.** It runs in the database's VPC: give it a NAT gateway or a Secrets Manager VPC interface endpoint.
- **Schedule:** 30 days is common. Each rotation makes cached passwords wrong until the retry above refetches them.

## Pitfalls
- **The rotated password in an env var.** A Lambda env var (including `{{resolve:secretsmanager:...}}`) is resolved at deploy time and frozen into the published version: it breaks at the first rotation and is readable via `GetFunctionConfiguration`.
- **Retrying on every connection error.** A database outage then takes twice as long to surface. Retry once, and only when the secret changed.
- **Ignoring `username`.** Alternating-users rotation changes it.

## Related
- [[2b-settings-db]]
- [[4a-settings-refreshing-values-cache]]
- [[1e-settings-lambda]]
