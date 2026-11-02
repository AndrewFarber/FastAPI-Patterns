---
title: "DB settings"
category: persistence
tags: [settings, database, postgres, sqlalchemy]
status: draft
related: ["[[0-settings-guide]]", "[[1a-settings-management]]", "[[2b-settings-db-rds-tls]]", "[[2b-settings-db-iam-auth]]", "[[2b-settings-db-rotated-password]]", "[[2b-settings-db-cdk-rotation]]", "[[1e-settings-lambda]]"]
---

# DB settings

## Problem
Database configuration holds the app's most sensitive value (the password) and the one most often malformed (the connection URL). A single URL string leaks the password in logs and breaks on special characters, and connections without certificate verification can be intercepted.

## Use when
- The app connects to PostgreSQL through SQLAlchemy and loads configuration as in [[1a-settings-management]].

## Avoid when
- Another database or driver: keep the structure, but change the `scheme`, the DSN type (e.g. `MySQLDsn`), and the TLS details.

## Solution

### The settings model
```python
# app/config/db.py
from typing import Annotated, Literal, Self
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, FilePath, PostgresDsn, SecretStr, model_validator

from app.config.db_iam import IamAuth
from app.config.db_rotated import RotatedSecretAuth


class PasswordAuth(BaseModel):
    """A static password."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["password"]
    password: SecretStr


# One model per authentication method, selected by its "method" value.
# IamAuth: 2b-settings-db-iam-auth. RotatedSecretAuth: 2b-settings-db-rotated-password.
DbAuth = Annotated[PasswordAuth | IamAuth | RotatedSecretAuth, Field(discriminator="method")]


class DbSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Connection parts
    scheme: Literal["postgresql+psycopg"] = "postgresql+psycopg"
    host: str
    port: int = Field(default=5432, gt=0, le=65535)
    user: str
    name: str
    auth: DbAuth

    # TLS: verify the server certificate by default
    sslmode: Literal["disable", "require", "verify-ca", "verify-full"] = "verify-full"
    # A CA bundle file shipped in the image (2b-settings-db-rds-tls). Not "system":
    # psycopg[binary]'s bundled OpenSSL looks for the OS trust store in a path that doesn't exist
    sslrootcert: FilePath | None = None

    # Pool tuning. On Lambda: pool_size=1, max_overflow=0 (one request at a time per environment)
    pool_size: int = Field(default=5, gt=0)
    max_overflow: int = Field(default=10, ge=0)
    pool_timeout_seconds: float = Field(default=30, gt=0)
    pool_recycle_seconds: int = Field(default=1800, gt=0)          # replace connections older than this
    connect_timeout_seconds: int = Field(default=10, gt=0)         # fail fast when the DB is unreachable
    echo: bool = False

    @model_validator(mode="after")
    def check_tls(self) -> Self:
        if self.sslmode.startswith("verify") and self.sslrootcert is None:
            raise ValueError("sslrootcert is required when sslmode verifies the certificate")
        return self

    @property
    def url(self) -> PostgresDsn:
        # A plain @property, not @computed_field: computed fields appear in
        # repr() and model_dump(), which would leak the password.
        password = self.auth.password.get_secret_value() if isinstance(self.auth, PasswordAuth) else None
        return PostgresDsn.build(
            scheme=self.scheme,
            username=self.user,
            password=quote(password, safe="") if password else None,  # build() doesn't escape @ / : %
            host=self.host,
            port=self.port,
            path=self.name,
        )

    def connect_args(self, application_name: str) -> dict[str, str | int]:
        """libpq parameters for SQLAlchemy's connect_args: TLS, timeout, and a name for pg_stat_activity."""
        args: dict[str, str | int] = {
            "sslmode": self.sslmode,
            "connect_timeout": self.connect_timeout_seconds,
            "application_name": application_name,
        }
        if self.sslrootcert is not None:
            args["sslrootcert"] = str(self.sslrootcert)
        return args
```

```python
# app/db/engine.py
from sqlalchemy import Engine, create_engine

from app.config.db import DbSettings
from app.config.db_iam import IamAuth
from app.config.db_rotated import RotatedSecretAuth
from app.db.iam_auth import add_iam_token
from app.db.rotated_password import add_rotated_password


def build_engine(db: DbSettings, application_name: str) -> Engine:
    engine = create_engine(
        str(db.url),
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_timeout=db.pool_timeout_seconds,
        pool_recycle=db.pool_recycle_seconds,
        pool_pre_ping=True,               # drop dead connections before use
        echo=db.echo,
        connect_args=db.connect_args(application_name),
    )
    # Auth methods without a static password supply it per connection
    if isinstance(db.auth, IamAuth):
        add_iam_token(engine, db)
    elif isinstance(db.auth, RotatedSecretAuth):
        add_rotated_password(engine, db)
    return engine
```

The engine is created once in the lifespan and disposed on shutdown (the full `app/main.py` is in [[1b-settings-access]]):

```python
# app/main.py (fragment)
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    app.state.engine = build_engine(settings.db, application_name=settings.app.name)
    yield
    app.state.engine.dispose()
```

```bash
# Local development. Deployed: no password in env vars, use a rotated secret or IAM
DB__HOST=localhost
DB__USER=app
DB__NAME=orders
DB__AUTH__METHOD=password
DB__AUTH__PASSWORD=app
# Local Postgres has no TLS
DB__SSLMODE=disable
```

- **Pydantic features used:** `PostgresDsn` validates the URL; `SecretStr` masks the password; `FilePath` checks the CA bundle exists at startup; `Field` constraints validate ports and pool sizes; `Literal` rejects unsupported schemes and SSL modes; a discriminated union picks the auth model from `method`.
- **Parts, not one URL field.** A single `url: PostgresDsn` field would print the password in reprs and logs. Storing parts keeps the password in a `SecretStr` and builds the URL only when the engine needs it.
- **Auth as a discriminated union.** Each method is its own model with only the fields it needs, so `extra="forbid"` rejects a password set alongside IAM auth. `PasswordAuth` is defined here; the other methods have their own modules and notes, and `build_engine()` adds their connect hooks.
- **Secure by default.** `sslmode` defaults to `verify-full`, so a deployment that forgets TLS settings fails at startup instead of connecting unverified. Local development opts out explicitly.
- **`application_name`** identifies the app in `pg_stat_activity` and the Postgres logs.

### Pool on Lambda
Each execution environment handles one request at a time, so one connection is enough. The defaults (5 + 10) suit a long-lived server.

```bash
DB__POOL_SIZE=1
DB__MAX_OVERFLOW=0
```

- **`pool_pre_ping`** (always on in `build_engine()`) replaces the connection when it died while the environment was frozen between requests.
- **RDS Proxy.** A burst of new environments still opens one connection each; the proxy absorbs that ([[2b-settings-db-rds-tls]]).
- The engine is built during init and disposed on SIGTERM; see [[1e-settings-lambda]].

### Specific capabilities
| Need | Note |
|---|---|
| TLS to Amazon RDS, RDS Proxy | [[2b-settings-db-rds-tls]] |
| No password: AWS IAM database authentication | [[2b-settings-db-iam-auth]] |
| Password rotated by Secrets Manager, picked up without a restart | [[2b-settings-db-rotated-password]] |
| Setting up rotation with AWS CDK | [[2b-settings-db-cdk-rotation]] |

## Pitfalls
- **One `url` field.** `url: PostgresDsn` prints the password in reprs and logs; store parts and build the URL.
- **`@computed_field` for the URL.** Computed fields are included in `repr()` and `model_dump()`, which leaks the password. Use a plain `@property`.
- **Unescaped passwords.** `PostgresDsn.build()` doesn't URL-encode, so `@`, `/`, `:` or `%` in a password produce a broken URL. Always `quote(password, safe="")`.
- **`sslmode=require` in production.** It encrypts but doesn't verify the server, so it doesn't stop a man-in-the-middle. Use `verify-full` with the server's CA bundle.
- **Default pool sizes on Lambda.** Up to 15 connections per environment, times hundreds of environments, exhausts the database. Set 1 and 0.
- **One flat model with every auth field optional.** It needs cross-field validators for each method and still accepts nonsense combinations. Use one model per method.

## Related
- [[0-settings-guide]]
- [[1a-settings-management]]
- [[2b-settings-db-rds-tls]]
- [[2b-settings-db-iam-auth]]
- [[2b-settings-db-rotated-password]]
- [[2b-settings-db-cdk-rotation]]
- [[1e-settings-lambda]]
