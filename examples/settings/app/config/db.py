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

    # Pool tuning: pool_size + max_overflow, times the number of instances, must fit max_connections
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
