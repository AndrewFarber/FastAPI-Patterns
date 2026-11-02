---
title: "Rotated DB passwords"
category: persistence
tags: [settings, database, secrets-rotation, secrets-manager]
status: draft
related: ["[[2b-settings-db]]", "[[2b-settings-db-iam-auth]]", "[[4a-settings-refreshing-values-cache]]"]
---

# Rotated DB passwords

Settings hold the secret's ID, not the password. A `do_connect` hook reads the current credentials from a TTL cache per new connection, and retries once if the secret changed. The app keeps connecting through a rotation without a restart.

## Fits when
- The DB password lives in Secrets Manager with rotation enabled.

Not when:
- IAM authentication is possible: nothing to rotate ([[2b-settings-db-iam-auth]]).
- The password never rotates: `PasswordAuth` ([[2b-settings-db]]).

## Signals
- **Feature:** "rotate the DB password", "Secrets Manager rotation", connections failing after a rotation.
- **Code:** the password read once at startup into `PasswordAuth` or an env var; `{{resolve:secretsmanager:...}}` in deploy config; `get_secret_value` without a cache on every connection.

## Pattern
```python
# app/core/config/db_rotated.py
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RotatedSecretAuth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["rotated_secret"]
    secret_id: str
    region: str
    ttl_seconds: float = Field(default=300, gt=0)
```

```python
# app/core/db/rotated_password.py
import json

import psycopg
from sqlalchemy import Engine, event

from app.core.aws.values import secrets_manager_cache
from app.core.config.db import DbSettings
from app.core.config.db_rotated import RotatedSecretAuth


def add_rotated_password(engine: Engine, db: DbSettings) -> None:
    assert isinstance(db.auth, RotatedSecretAuth)
    auth = db.auth
    secrets = secrets_manager_cache(auth.region, auth.ttl_seconds)

    @event.listens_for(engine, "do_connect")
    def connect_with_current_password(dialect, conn_rec, cargs, cparams):
        secret = json.loads(secrets.get(auth.secret_id))
        cparams["user"] = secret["username"]
        cparams["password"] = secret["password"]
        try:
            return dialect.connect(*cargs, **cparams)
        except psycopg.OperationalError:
            secrets.invalidate(auth.secret_id)
            fresh = json.loads(secrets.get(auth.secret_id))
            if fresh == secret:
                raise
        cparams["user"] = fresh["username"]
        cparams["password"] = fresh["password"]
        return dialect.connect(*cargs, **cparams)
```

`build_engine()` ([[2b-settings-db]]) calls `add_rotated_password()` when `db.auth` is a `RotatedSecretAuth`.

## Rules
- **Read per new connection, through the cache** ([[4a-settings-refreshing-values-cache]]). Pooled connections stay open.
- **Retry once, only when the secret changed.** libpq gives connection errors no SQLSTATE, so an auth failure looks like an outage; comparing secrets keeps an outage to one timeout.
- **Take `username` from the secret too.** Alternating-users rotation switches between two users.
- **Prefer alternating users.** With single-user rotation, the database has the new password a few seconds before `AWSCURRENT` does; new connections in that window fail, and the retry can't help because the secret hasn't changed yet. Open pooled connections are unaffected.
- **The app user gets its own secret,** never the master's.

## Anti-patterns
- **The password in an env var.** Frozen at deploy, broken at the first rotation, readable in the deployment configuration.
- **Retrying on every connection error.** A database outage takes twice as long to surface.

## Related
- [[2b-settings-db]]
- [[2b-settings-db-iam-auth]]
- [[4a-settings-refreshing-values-cache]]
