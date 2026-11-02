from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, model_validator


class EmailSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    smtp_host: str
    smtp_port: int = Field(default=587, gt=0, le=65535)
    security: Literal["starttls", "tls", "none"] = "starttls"   # 587: starttls, 465: tls
    username: str | None = None
    password: SecretStr | None = None                           # deployed: from Secrets Manager, not a plain env var
    from_address: EmailStr                                      # needs the email-validator package

    @model_validator(mode="after")
    def check_consistent(self) -> Self:
        if (self.username is None) != (self.password is None):
            raise ValueError("set both username and password, or neither")
        if self.username is not None and self.security == "none":
            raise ValueError("credentials need security='starttls' or 'tls'")
        if (self.smtp_port, self.security) in ((465, "starttls"), (587, "tls")):
            raise ValueError(f"port {self.smtp_port} doesn't use security={self.security!r}")
        return self
