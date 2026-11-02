---
title: "DB settings"
category: persistence
related:
  - "[[settings-guide]]"
  - "[[settings-db-iam-auth]]"
  - "[[settings-management]]"
  - "[[settings-access]]"
---

# DB settings

## Overview
Store connection *parts*, not a URL, with authentication as a discriminated union of one model per method, and verified TLS by default. Deployed environments use IAM ([[settings-db-iam-auth]]); a static password, kept in a `SecretStr`, is for local development and tests only.

## Rules
- **Parts, not a URL.** `url` is a plain `@property` that `quote()`s the password; a computed field would appear in `repr()` and `model_dump()`.
- **One auth model per method,** selected by `method`. `extra="forbid"` then rejects a password set alongside IAM.
- **`password` locally, `iam` when deployed.** The root validator rejects `PasswordAuth` when `app.is_prd` ([[settings-management]]); IAM adds its token hook in `build_engine()` ([[settings-db-iam-auth]]).
- **Secure by default:** `sslmode` defaults to `verify-full` and requires `sslrootcert`; local development opts out with `DB__SSLMODE=disable`.
- **`sslrootcert` is a CA bundle file in the image** (`FilePath`, checked at startup), not `system`: `psycopg[binary]`'s bundled OpenSSL looks for the OS store at a path that doesn't exist. For Amazon RDS use the RDS global bundle. Trust roots, never intermediates.
- **`host` is the real endpoint.** `verify-full` and IAM tokens check it; a DNS alias fails.
- **`pool_pre_ping=True` always,** and `application_name` set for `pg_stat_activity`.
- **Size the pool for every instance:** `pool_size + max_overflow`, times the number of app instances, must stay under the database's `max_connections`.

## Code example
```python
# app/core/config/db.py
from typing import Annotated, Literal, Self
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, FilePath, PostgresDsn, SecretStr, model_validator

from app.core.config.db_iam import IamAuth


class PasswordAuth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["password"]
    password: SecretStr


DbAuth = Annotated[PasswordAuth | IamAuth, Field(discriminator="method")]


class DbSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scheme: Literal["postgresql+psycopg"] = "postgresql+psycopg"
    host: str
    port: int = Field(default=5432, gt=0, le=65535)
    user: str
    name: str
    auth: DbAuth

    sslmode: Literal["disable", "require", "verify-ca", "verify-full"] = "verify-full"
    sslrootcert: FilePath | None = None

    pool_size: int = Field(default=5, gt=0)
    max_overflow: int = Field(default=10, ge=0)
    pool_timeout_seconds: float = Field(default=30, gt=0)
    pool_recycle_seconds: int = Field(default=1800, gt=0)
    connect_timeout_seconds: int = Field(default=10, gt=0)
    echo: bool = False

    @model_validator(mode="after")
    def check_tls(self) -> Self:
        if self.sslmode.startswith("verify") and self.sslrootcert is None:
            raise ValueError("sslrootcert is required when sslmode verifies the certificate")
        return self

    @property
    def url(self) -> PostgresDsn:
        password = self.auth.password.get_secret_value() if isinstance(self.auth, PasswordAuth) else None
        return PostgresDsn.build(
            scheme=self.scheme,
            username=self.user,
            password=quote(password, safe="") if password else None,
            host=self.host,
            port=self.port,
            path=self.name,
        )

    def connect_args(self, application_name: str) -> dict[str, str | int]:
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
# app/core/db/engine.py
from sqlalchemy import Engine, create_engine

from app.core.config.db import DbSettings
from app.core.config.db_iam import IamAuth
from app.core.db.iam_auth import add_iam_token


def build_engine(db: DbSettings, application_name: str) -> Engine:
    engine = create_engine(
        str(db.url),
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_timeout=db.pool_timeout_seconds,
        pool_recycle=db.pool_recycle_seconds,
        pool_pre_ping=True,
        echo=db.echo,
        connect_args=db.connect_args(application_name),
    )
    if isinstance(db.auth, IamAuth):
        add_iam_token(engine, db)
    return engine
```

The engine is built once in the lifespan and disposed on shutdown ([[settings-access]]).
