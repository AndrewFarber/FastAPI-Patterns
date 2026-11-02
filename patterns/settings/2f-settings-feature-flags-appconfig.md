---
title: "Runtime feature flags"
category: project-structure
tags: [settings, feature-flags, aws-appconfig]
status: draft
related: ["[[2f-settings-feature-flags]]", "[[1e-settings-lambda]]", "[[1d-settings-deployments-appconfig-rollouts]]", "[[4a-settings-refreshing-values]]"]
---

# Runtime feature flags

## Problem
Kill switches and gradual rollouts must change within minutes, without a deploy. Static flags in `FeatureSettings` ([[2f-settings-feature-flags]]) only change on redeploy.

## Use when
- A flag must change while the app runs: kill switches, gradual rollouts, operational toggles.

## Avoid when
- The flag only changes per environment or release. Use static flags ([[2f-settings-feature-flags]]).

## Solution
AWS AppConfig holds flags that change without a deploy. On Lambda, AWS ships AppConfig Agent as a Lambda extension: added to the container image, it starts with each execution environment, fetches the flags, caches them, refreshes them at most every `AWS_APPCONFIG_EXTENSION_POLL_INTERVAL_SECONDS` (45 s by default), and serves them on `localhost:2772`. The app makes a cheap local HTTP call per read.

### Add the extension to the image
AWS publishes the agent as a Lambda layer; a container image can't use layers, so the build unzips the layer into `/opt`. Download it next to the Dockerfile first, for the function's region and architecture (layer ARNs are listed in the AppConfig docs):

```bash
aws lambda get-layer-version-by-arn \
  --arn arn:aws:lambda:us-east-1:027255383542:layer:AWS-AppConfig-Extension:<version> \
  --query Content.Location --output text | xargs curl -o settings/appconfig-extension.zip
```

```dockerfile
# Dockerfile (fragment)
FROM public.ecr.aws/docker/library/python:3.14-slim AS appconfig-extension
RUN apt-get update && apt-get install -y --no-install-recommends unzip   # keeps the binaries' exec bits
COPY settings/appconfig-extension.zip /tmp/
RUN unzip /tmp/appconfig-extension.zip -d /opt

FROM public.ecr.aws/docker/library/python:3.14-slim
# COPY merges into /opt: the agent lands next to the Lambda Web Adapter in /opt/extensions
COPY --from=appconfig-extension /opt /opt
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0 /lambda-adapter /opt/extensions/lambda-adapter
```

### Point the function at it
```python
# infra/service_stack.py (fragment)
environment={
    # Where the app reads the runtime flags: the AppConfig environment is named per stage
    "FEATURES__RUNTIME_FLAGS__APPLICATION": "orders-api",
    "FEATURES__RUNTIME_FLAGS__ENVIRONMENT": appconfig_environment,
    # The agent fetches these during its own init, before the app's, so the first read is a cache hit
    "AWS_APPCONFIG_EXTENSION_PREFETCH_LIST": (
        f"/applications/orders-api/environments/{appconfig_environment}/configurations/runtime-flags"
    ),
},
...
# The AppConfig agent extension calls AppConfig with the function's role
self.function.add_to_role_policy(iam.PolicyStatement(
    actions=["appconfig:StartConfigurationSession", "appconfig:GetLatestConfiguration"],
    resources=[f"arn:{self.partition}:appconfig:{self.region}:{self.account}:application/*"],
))
```

`FEATURES__RUNTIME_FLAGS__*` fills `FeatureSettings.runtime_flags` ([[2f-settings-feature-flags]]). Locally it stays unset: no agent, no HTTP calls, flags keep their defaults.

### Read the flags in the app

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

- **Typed flags,** as with static flags: `flags.payments_kill_switch`, not a string lookup.
- **Fail safe:** defaults are the safe state (kill switch off means payments on; rollouts off). A failed read (agent down or slow, a payload that isn't `{"flag": {"enabled": bool}}`) keeps the last good flags, logs one warning, and skips the agent for `retry_after_seconds` so requests don't each wait on it.
- **One client per execution environment,** cached like `get_settings()` ([[1b-settings-access]]); nothing on `app.state`. Each environment's agent polls on its own, so for up to one poll interval some environments see a flag change before others ([[1e-settings-lambda]]).
- The agent handles AppConfig authentication, polling, and caching; the app never calls the AppConfig API.
- **Roll flag changes out gradually** with an AppConfig deployment strategy, so a bad flag can be caught and rolled back ([[1d-settings-deployments-appconfig-rollouts]]).

## Pitfalls
- **Unsafe defaults.** Until the first successful read, and whenever reads fail with nothing cached, flags take their defaults. Make the default the safe state.
- **Silent failures.** A broken agent leaves flags frozen at their last values. Alert on the warning.
- **No extension in the image, or no IAM permissions.** Every read fails and every flag stays at its default, with no error at init. The warning in the logs is the only sign.
- **Deriving the AppConfig environment from `is_prd`.** `"prd" if is_prd else "dev"` points staging at dev's flags. Name the environment per stage.
- **Forgetting `FEATURES__RUNTIME_FLAGS__*` in a deployed stage.** The app then never asks the agent and flags keep their defaults. The stack sets them next to `AWS_APPCONFIG_EXTENSION_PREFETCH_LIST`.
- **Mixing static and runtime flags.** Keep release toggles in `FeatureSettings`; only operational toggles belong here.

## Related
- [[2f-settings-feature-flags]]
- [[1e-settings-lambda]]
- [[1d-settings-deployments-appconfig-rollouts]]
- [[4a-settings-refreshing-values]]
