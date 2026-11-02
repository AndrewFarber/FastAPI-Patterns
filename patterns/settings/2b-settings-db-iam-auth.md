---
title: "IAM database authentication"
category: persistence
tags: [settings, database, aws-rds, aws-iam]
status: draft
related: ["[[2b-settings-db]]"]
---

# IAM database authentication

Settings hold only *how* to authenticate (`method: iam`, region); a SQLAlchemy `do_connect` hook signs a fresh 15-minute token per new connection. The app has no DB password to store or rotate.

## Fits when
- Always, when deployed: the app connects to Amazon RDS or Aurora PostgreSQL and runs with an AWS role. Local runs and tests use `PasswordAuth` ([[2b-settings-db]]).

Not when:
- The database isn't on AWS: this vault doesn't cover it.

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
- **Keep new connections under about 200 per second:** RDS throttles IAM authentication. Size the pool so connections are reused ([[2b-settings-db]]); put RDS Proxy in front if instances churn.
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
