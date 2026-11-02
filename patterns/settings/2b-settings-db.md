---
title: "DB settings"
category: persistence
tags: [settings, database, postgres, sqlalchemy]
status: draft
related: ["[[0-settings-guide]]", "[[1a-settings-management]]", "[[2b-settings-db-iam-auth]]", "[[2b-settings-db-rotated-password]]"]
---

# DB settings

Store connection *parts*, not a URL, with authentication as a discriminated union of one model per method, and verified TLS by default. The password stays in a `SecretStr`, the URL is built only for the engine, and each auth method accepts only its own fields.

## Fits when
- The app connects to PostgreSQL through SQLAlchemy and uses [[1a-settings-management]].

Not when:
- Another database: keep the structure, change `scheme`, the DSN type (`MySQLDsn`), and the TLS fields.

## Signals
- **Feature:** connecting to a database, adding a DB auth method, TLS to the database, pool tuning.
- **Code:** `DATABASE_URL` or `url: PostgresDsn` as a field; `create_engine(os.getenv(...))`; `@computed_field` URL; `sslmode=require`; one model with `password`, `iam_region`, `secret_id` all optional; the engine created per request.

## Pattern
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
    # A CA bundle file shipped in the image (2b-settings-db). Not "system":
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

The engine is built once in the lifespan and disposed on shutdown ([[1b-settings-access]]).

## Rules
- **Parts, not a URL.** `url` is a plain `@property` that `quote()`s the password; a computed field would appear in `repr()` and `model_dump()`.
- **One auth model per method,** selected by `method`. `extra="forbid"` then rejects a password set alongside IAM. Methods without a static password add a connect hook in `build_engine()` ([[2b-settings-db-iam-auth]], [[2b-settings-db-rotated-password]]).
- **Secure by default:** `sslmode` defaults to `verify-full` and requires `sslrootcert`; local development opts out with `DB__SSLMODE=disable`.
- **`sslrootcert` is a CA bundle file in the image** (`FilePath`, checked at startup), not `system`: `psycopg[binary]`'s bundled OpenSSL looks for the OS store at a path that doesn't exist. For Amazon RDS use the RDS global bundle; for RDS Proxy the Amazon Root CAs. Trust roots, never intermediates.
- **`host` is the real endpoint.** `verify-full` and IAM tokens check it; a DNS alias fails.
- **`pool_pre_ping=True` always,** and `application_name` set for `pg_stat_activity`.
- **On Lambda: `DB__POOL_SIZE=1`, `DB__MAX_OVERFLOW=0`** (one request at a time per instance), with RDS Proxy in front to absorb bursts of new instances.

## Anti-patterns
- **A single `url` field.** Prints the password in reprs and logs.
- **Unescaped passwords.** `PostgresDsn.build()` doesn't encode `@ / : %`.
- **`sslmode=require` in production.** Encrypts but doesn't verify the server.
- **Default pool sizes on Lambda.** 15 connections per instance times hundreds of instances exhausts the database.
- **One flat model with every auth field optional.** Needs a validator per method and still accepts nonsense combinations.

## Related
- [[0-settings-guide]]
- [[1a-settings-management]]
- [[2b-settings-db-iam-auth]]
- [[2b-settings-db-rotated-password]]
