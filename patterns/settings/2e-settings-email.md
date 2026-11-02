---
title: "Email settings"
category: project-structure
tags: [settings, email, smtp]
status: draft
related: ["[[1a-settings-management]]", "[[3b-settings-aws-sources-pydantic]]"]
---

# Email settings

## Problem
SMTP configuration is easy to get subtly wrong: a port that doesn't match the TLS mode, a username without a password, an invalid sender address that only fails at the first send.

## Use when
- The app sends email over SMTP.

## Avoid when
- The app runs on AWS and sends through SES: use the SES v2 API (`boto3.client("sesv2").send_email`) with the function's role instead. SES SMTP credentials are a long-lived IAM access key that has to be stored and rotated by hand; the role needs neither.
- The app sends through another provider's HTTP API. That needs an HTTP client, not SMTP settings.

## Solution
```python
# app/config/email.py
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
```

```python
# app/config/settings.py (fragment)
    email: EmailSettings | None = None   # None = email disabled
```

```bash
# Local development: a mail catcher such as Mailpit, no credentials
EMAIL__SMTP_HOST=localhost
EMAIL__SMTP_PORT=1025
EMAIL__SECURITY=none
EMAIL__FROM_ADDRESS=orders@example.com
```

- **Optional subsystem.** With no `EMAIL__*` set, `settings.email` is `None` and code skips sending. Setting any of them requires `smtp_host` and `from_address`.
- **The validator rejects inconsistent combinations at startup:** a username without a password (or the reverse), credentials with `security="none"`, STARTTLS on 465 and TLS on 587.
- **`security` instead of a `use_tls` bool.** Port 587 uses STARTTLS, port 465 uses TLS from the start; a bool can't say which.
- **The password is a secret.** In deployed environments it goes into the app's Secrets Manager secret as `email--password`, read at init ([[3b-settings-aws-sources-pydantic]]), not into a plain `EMAIL__PASSWORD` env var ([[1a-settings-management]]). Host, port and sender stay ordinary env vars.

## Pitfalls
- **Port and security mismatch.** STARTTLS on 465 or TLS on 587 hangs or fails the handshake. The validator catches the standard ports; a custom port is up to you.
- **`security="none"` outside local development.** Mail goes over the network in plain text; with credentials the validator rejects it.
- **SMTP credentials in the function's env vars.** Anyone with `lambda:GetFunctionConfiguration` can read them ([[1e-settings-lambda]]).

## Related
- [[1a-settings-management]]
- [[3b-settings-aws-sources-pydantic]]
