---
title: "Runtime feature flags"
category: project-structure
tags: [settings, feature-flags, aws-appconfig]
status: draft
related: ["[[2f-settings-feature-flags]]", "[[1d-settings-deployments]]", "[[4a-settings-refreshing-values]]"]
---

# Runtime feature flags

Flags that change without a deploy are a typed `RuntimeFlags` model read from the AppConfig Agent on localhost, through a client cached per process and a `RuntimeFlagsDep`. Defaults are the safe state, and a failed read keeps the last good flags.

## Fits when
- A flag must change while the app runs: kill switches, gradual rollouts, operational toggles.

Not when:
- It only changes per environment or release: [[2f-settings-feature-flags]].

## Signals
- **Feature:** "kill switch", "turn it off without a deploy", "roll out to 10%".
- **Code:** calls to the AppConfig API (`appconfigdata`) from the app; flags as `dict[str, bool]` lookups; flag reads that raise on failure; runtime flags mixed into `FeatureSettings`.

## Pattern
`FeatureSettings.runtime_flags` ([[2f-settings-feature-flags]]) says where the agent finds the flags; unset locally, so flags keep their defaults.

```python
# app/clients/runtime_flags.py
import http.client
import logging
import time
import urllib.request

from pydantic import BaseModel, ConfigDict, TypeAdapter

logger = logging.getLogger(__name__)


class RuntimeFlags(BaseModel):
    """Flags that change without a deploy. Static flags stay in FeatureSettings."""

    model_config = ConfigDict(frozen=True, extra="ignore")   # flags added in AppConfig first are ignored

    payments_kill_switch: bool = False
    new_checkout_rollout: bool = False


class _Flag(BaseModel):
    model_config = ConfigDict(extra="ignore")                 # flag attributes besides "enabled" are ignored

    enabled: bool


# A feature flag profile, as the agent serves it: {"payments_kill_switch": {"enabled": true}, ...}
_payload = TypeAdapter(dict[str, _Flag])


class AppConfigFlags:
    """Reads RuntimeFlags from AppConfig Agent on localhost. One per process (on Lambda: per execution environment)."""

    def __init__(
        self, application: str, environment: str, profile: str,
        timeout_seconds: float = 0.5, retry_after_seconds: float = 10.0,
    ) -> None:
        self._url = (
            f"http://localhost:2772/applications/{application}"
            f"/environments/{environment}/configurations/{profile}"
        )
        self._timeout = timeout_seconds
        self._retry_after = retry_after_seconds
        self._retry_at = 0.0
        self._last = RuntimeFlags()                           # all off until the first successful read

    def get(self) -> RuntimeFlags:
        if time.monotonic() < self._retry_at:
            return self._last                                 # the agent failed recently: don't wait on it every request
        try:
            with urllib.request.urlopen(self._url, timeout=self._timeout) as response:
                payload = _payload.validate_json(response.read())
            self._last = RuntimeFlags.model_validate({name: flag.enabled for name, flag in payload.items()})
        # Agent down or slow, broken response, or a payload of the wrong shape (ValidationError is a ValueError)
        except (OSError, http.client.HTTPException, ValueError) as exc:
            self._retry_at = time.monotonic() + self._retry_after
            logger.warning("reading flags from AppConfig Agent failed, using the last good flags: %s", exc)
        return self._last
```

```python
# app/dependencies/flags.py
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.clients.runtime_flags import AppConfigFlags, RuntimeFlags
from app.config.settings import get_settings


@lru_cache
def get_appconfig_flags() -> AppConfigFlags | None:
    """One client per process (on Lambda: per execution environment), like get_settings()."""
    source = get_settings().features.runtime_flags
    return AppConfigFlags(source.application, source.environment, source.profile) if source else None


def get_runtime_flags() -> RuntimeFlags:
    client = get_appconfig_flags()
    return client.get() if client else RuntimeFlags()        # no AppConfig configured: safe defaults


RuntimeFlagsDep = Annotated[RuntimeFlags, Depends(get_runtime_flags)]
```

## Rules
- **Typed flags,** like static ones: `flags.payments_kill_switch`.
- **Safe defaults:** kill switch off = payments on, rollouts off. They apply until the first read and whenever reads fail with nothing cached.
- **Fail safe, fail quiet, back off:** a failed read logs one warning, keeps the last good flags, and skips the agent for `retry_after_seconds`.
- **`extra="ignore"` on `RuntimeFlags`,** unlike settings: a flag can be added in AppConfig before the code that reads it.
- **One client per process,** `lru_cache`d like `get_settings()`; nothing on `app.state`.
- **The agent does auth, polling, and caching.** On Lambda it's an extension in `/opt/extensions`; the role needs `appconfig:StartConfigurationSession` and `GetLatestConfiguration` on the profile.
- **Roll flag changes out with an AppConfig deployment strategy** (e.g. linear 20%), with alarms that roll it back. The app's canary doesn't cover them ([[1d-settings-deployments]]). Kill switches use `AllAtOnce`, ideally in their own AppConfig environment so a running rollout can't block them.

## Anti-patterns
- **Unsafe defaults.** A broken agent turns them on.
- **Silent failures.** Alert on the warning: no agent or no IAM permission leaves every flag at its default with no startup error.
- **Deriving the AppConfig environment from `is_prd`.** Name it per stage.

## Related
- [[2f-settings-feature-flags]]
- [[1d-settings-deployments]]
- [[4a-settings-refreshing-values]]
