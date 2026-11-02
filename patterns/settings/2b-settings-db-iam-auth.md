---
title: "IAM database authentication"
category: persistence
tags: [settings, database, aws-rds, aws-iam]
status: draft
related: ["[[2b-settings-db]]", "[[2b-settings-db-rds-tls]]", "[[2b-settings-db-rotated-password]]", "[[1e-settings-lambda]]"]
---

# IAM database authentication

## Problem
A DB password has to be stored, distributed, and rotated. With RDS IAM authentication the app has no DB password at all: it signs a short-lived token (valid 15 minutes) with its AWS credentials and uses it as the password for each new connection.

## Use when
- The app connects to Amazon RDS, Aurora PostgreSQL, or RDS Proxy and runs with an AWS role (on Lambda, the function's execution role).

## Avoid when
- More than about 200 new connections per second straight to the database (AWS's guidance): put RDS Proxy in front (below).
- The database isn't on AWS, or tools that connect to it can't generate tokens. Use a password ([[2b-settings-db]]), rotated if possible ([[2b-settings-db-rotated-password]]).

## Solution
`IamAuth` has its own module and is part of the `DbAuth` union in `app/config/db.py` ([[2b-settings-db]]):

```python
# app/config/db_iam.py
from typing import Literal

from pydantic import BaseModel, ConfigDict


class IamAuth(BaseModel):
    """AWS IAM database authentication: a fresh token per connection, no password."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["iam"]
    region: str                                     # region of the RDS instance or RDS Proxy
```

Since tokens expire, they can't live in settings; the engine creates one per connection through SQLAlchemy's `do_connect` event:

```python
# app/db/iam_auth.py
import boto3
from sqlalchemy import Engine, event

from app.config.db import DbSettings
from app.config.db_iam import IamAuth


def add_iam_token(engine: Engine, db: DbSettings) -> None:
    """Use a fresh IAM auth token as the password for each new connection."""
    assert isinstance(db.auth, IamAuth)
    if db.sslmode == "disable":
        raise ValueError("IAM database authentication requires TLS")
    rds = boto3.client("rds", region_name=db.auth.region)

    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        # Signed locally with the app's AWS credentials: no network call.
        # boto3 refreshes role credentials itself, so the client can be reused.
        cparams["password"] = rds.generate_db_auth_token(
            DBHostname=db.host, Port=db.port, DBUsername=db.user, Region=db.auth.region
        )
```

`build_engine()` ([[2b-settings-db]]) calls `add_iam_token()` when `db.auth` is an `IamAuth`.

```bash
DB__HOST=orders.abc123.us-east-1.rds.amazonaws.com
DB__USER=orders_app
DB__NAME=orders
DB__AUTH__METHOD=iam
DB__AUTH__REGION=us-east-1
DB__SSLMODE=verify-full
DB__SSLROOTCERT=/etc/ssl/certs/rds-global-bundle.pem
```

- **Token lifetime only matters at connect time.** The token is only used to authenticate; established sessions keep running after it expires. Each *new* connection gets a fresh token.
- **TLS is required**, verified against the RDS bundle ([[2b-settings-db-rds-tls]]).
- **No secret to read.** On Lambda, the function's role signs tokens locally, so init makes no Secrets Manager call ([[1e-settings-lambda]]).

### AWS setup
- IAM database authentication enabled on the instance.
- A dedicated DB user with the `rds_iam` role: `CREATE USER orders_app; GRANT rds_iam TO orders_app;`. Once a user has `rds_iam`, IAM auth takes precedence and that user can no longer log in with a password, so don't grant it to the master user.
- The app's role allowed `rds-db:connect` on `arn:aws:rds-db:<region>:<account>:dbuser:<DbiResourceId>/orders_app`.
- **Database capacity:** AWS advises 300 to 1000 MiB of extra memory on the DB instance for IAM authentication. On burstable instances, reduce other memory settings to compensate.
- **Auditing:** CloudWatch and CloudTrail don't log IAM DB authentication or token generation. Audit connections in the database; `application_name` identifies the app.

### Through RDS Proxy
Every new Lambda execution environment opens a connection, and each IAM connection costs the database CPU and memory. AWS recommends IAM database authentication below about 200 new connections per second; for bursty scale-out, authenticate to RDS Proxy instead. The code is unchanged; only the endpoint and CA differ:

```bash
DB__HOST=orders-proxy.proxy-abc123.us-east-1.rds.amazonaws.com
DB__AUTH__METHOD=iam
DB__SSLROOTCERT=/etc/ssl/certs/amazon-root-cas.pem
```

- The token is generated for the proxy endpoint, and the role needs `rds-db:connect` on the proxy (`dbuser:prx-<id>/orders_app`).
- The proxy connects to the database with the user's password from Secrets Manager, so the user keeps a password and must **not** have `rds_iam`. Only end-to-end IAM (proxy to database too) needs `rds_iam`.

## Pitfalls
- **IAM tokens in settings.** Tokens expire after 15 minutes; generate them per connection in `do_connect`, never at startup.
- **Custom DNS names for `host`.** Tokens must be generated for the RDS endpoint itself; a Route 53 alias fails.
- **Expired temporary credentials.** The AWS credentials that sign a token must still be valid when the connection is made. Let boto3 manage role credentials rather than passing static keys.
- **`rds_iam` on a user the proxy logs in with a password.** IAM auth then takes precedence and the proxy's connections fail. Grant `rds_iam` only for direct or end-to-end IAM.
- **Truncated tokens.** IAM tokens are about 1 KB or more. Drivers and tools that cap password length (some MySQL drivers do) fail authentication. psycopg has no such limit.

## Related
- [[2b-settings-db]]
- [[2b-settings-db-rds-tls]]
- [[2b-settings-db-rotated-password]]
- [[1e-settings-lambda]]
