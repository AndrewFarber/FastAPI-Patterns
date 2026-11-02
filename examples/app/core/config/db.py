from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FilePath,
    SecretStr,
    model_validator,
)

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

    sslmode: Literal["disable", "require", "verify-ca", "verify-full"] = (
        "verify-full"
    )
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
            raise ValueError(
                "sslrootcert is required when sslmode verifies the certificate"
            )
        return self
