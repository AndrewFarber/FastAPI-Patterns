---
title: "IAM database authentication"
category: persistence
tags: [settings, database, aws-rds, aws-iam]
status: draft
related: ["[[2b-settings-db]]", "[[2b-settings-db-rotated-password]]"]
---

# IAM database authentication

Settings hold only *how* to authenticate (`method: iam`, region); a SQLAlchemy `do_connect` hook signs a fresh 15-minute token per new connection. The app has no DB password to store or rotate.

## Fits when
- The app connects to Amazon RDS or Aurora PostgreSQL and runs with an AWS role.

Not when:
- More than about 200 new connections per second: RDS throttles IAM authentication; use [[2b-settings-db-rotated-password]].
- The database isn't on AWS, or other tools connecting to it can't generate tokens: [[2b-settings-db-rotated-password]].

## Signals
- **Feature:** "no DB password", "IAM auth", "connect with the app's role".
- **Code:** `generate_db_auth_token(` called once at startup or stored in settings; a token passed in `DATABASE_URL`; `boto3` imported in `core/config/`.

## Pattern
```python
# app/core/config/db_iam.py
from typing import Literal

from pydantic import BaseModel, ConfigDict


class IamAuth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["iam"]
    region: str
```

```python
# app/core/db/iam_auth.py
import boto3
from sqlalchemy import Engine, event

from app.core.config.db import DbSettings
from app.core.config.db_iam import IamAuth


def add_iam_token(engine: Engine, db: DbSettings) -> None:
    assert isinstance(db.auth, IamAuth)
    if db.sslmode == "disable":
        raise ValueError("IAM database authentication requires TLS")
    rds = boto3.client("rds", region_name=db.auth.region)

    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        cparams["password"] = rds.generate_db_auth_token(
            DBHostname=db.host, Port=db.port, DBUsername=db.user, Region=db.auth.region
        )
```

`build_engine()` ([[2b-settings-db]]) calls `add_iam_token()` when `db.auth` is an `IamAuth`.

## Rules
- **Token per connection, in `do_connect`.** It only authenticates; open sessions outlive it.
- **The auth model holds no secret,** only the method and region; the hook lives in `core/db/`, the model in `core/config/`.
- **TLS required:** the hook refuses `sslmode=disable`.
- **AWS side:** a dedicated DB user with `GRANT rds_iam`, and `rds-db:connect` on that user for the app's role.

## Anti-patterns
- **Tokens in settings or built at startup.** They expire after 15 minutes.
- **Static access keys.** Let boto3 manage role credentials, so the signing credentials are valid at connect time.
- **`rds_iam` on the master user.** IAM then takes precedence and its password stops working.

## Related
- [[2b-settings-db]]
- [[2b-settings-db-rotated-password]]
