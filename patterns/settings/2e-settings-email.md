---
title: "Email settings"
category: project-structure
tags: [settings, email, smtp]
status: draft
related: ["[[1a-settings-management]]", "[[3b-settings-aws-sources]]"]
---

# Email settings

An optional subsystem: `email: EmailSettings | None = None` on the root, with a validator that rejects inconsistent combinations (port vs TLS mode, username without password) at startup instead of at the first send.

## Fits when
- The app sends email over SMTP. The shape (optional sub-model + cross-field validator) fits any optional integration.

Not when:
- On AWS with SES: use the SES v2 API with the app's role; SMTP credentials are a long-lived key.
- A provider's HTTP API: that's a client in `clients/`, not SMTP settings.

## Signals
- **Feature:** "send email", "notifications by mail", any integration that may be switched off.
- **Code:** `email_enabled: bool` next to the email fields; `use_tls: bool`; sender as plain `str`; SMTP password as `str` or in a plain env var.

## Pattern
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

## Rules
- **`None` means disabled.** With no `EMAIL__*` set, code skips sending; setting any of them requires the rest.
- **`security: Literal["starttls", "tls", "none"]`, not `use_tls`.** 587 is STARTTLS, 465 is TLS; a bool can't say which.
- **Cross-field rules in one `model_validator`:** both-or-neither credentials, no credentials without TLS, standard ports match their mode.
- **`EmailStr`** for the sender (needs `email-validator`).
- **The password is a secret:** deployed, it comes from Secrets Manager as `email--password` ([[3b-settings-aws-sources]]).

## Anti-patterns
- **A separate `enabled` flag.** It can disagree with the fields.
- **`security="none"` outside local development.** Mail and credentials in plain text.

## Related
- [[1a-settings-management]]
- [[3b-settings-aws-sources]]
