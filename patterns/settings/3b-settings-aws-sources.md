---
title: "Settings from AWS sources"
category: project-structure
tags: [settings, aws, secrets-manager, parameter-store, pydantic-settings]
status: draft
related: ["[[1a-settings-management]]", "[[1c-settings-testing]]", "[[4a-settings-refreshing-values]]"]
---

# Settings from AWS sources

Read Secrets Manager and Parameter Store as pydantic-settings sources, added only when their env var is set. Values pass through the same validation as env vars, at startup, and local runs and tests need no AWS access.

## Fits when
- Secrets the app needs at startup, or more configuration than fits comfortably in env vars.

Not when:
- A few non-secret values: plain env vars set at deploy time, no AWS calls at startup.
- Values change while the app runs: these load once per process ([[4a-settings-refreshing-values]]).
- Local development and tests: plain env vars.

## Signals
- **Feature:** "read the secret from Secrets Manager", "too many env vars", "config in Parameter Store".
- **Code:** ad hoc `boto3` `get_secret_value` / `get_parameter` calls that fill settings by hand; secrets in deploy-time env vars or `{{resolve:secretsmanager:...}}`; a startup script that exports parameters as env vars.

## Pattern
```bash
uv add "pydantic-settings[aws-secrets-manager,aws-systems-manager]"
```

```python
# app/core/config/settings.py (fragment)
import os

from pydantic_settings import (
    AWSSecretsManagerSettingsSource,
    AWSSystemsManagerSettingsSource,
    BaseSettings,
    PydanticBaseSettingsSource,
)


class Settings(BaseSettings):
    ...

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        sources = [init_settings, env_settings]

        if secret_id := os.environ.get("AWS_SECRETS_MANAGER_SECRET_ID"):
            sources.append(AWSSecretsManagerSettingsSource(settings_cls, secret_id))
        if ssm_path := os.environ.get("AWS_SSM_PATH"):
            sources.append(AWSSystemsManagerSettingsSource(settings_cls, ssm_path))

        return tuple(sources)
```

```bash
# Deployed env vars; unset locally
AWS_SECRETS_MANAGER_SECRET_ID=shop/prd/app
AWS_SSM_PATH=/shop/prd
# The sources build their own boto3 clients: short connect timeout, standard retries
AWS_DEFAULTS_MODE=in-region
```

| | Secrets Manager | Parameter Store |
|---|---|---|
| Holds | Secrets | Plain configuration |
| Shape | One secret, a JSON object | One parameter per field under a path |
| Nested field | Key `db--auth--password` | `/shop/prd/db/host` |

## Where each value comes from
| Value | Source |
|---|---|
| Non-secret, few | Env var, set at deploy |
| Secret, or many values | These sources, at startup |
| Rotated DB password | Per connection: [[2b-settings-db-rotated-password]] |
| Changes while running | [[4a-settings-refreshing-values]] |

## Rules
- **Opt-in by env var,** so the fixtures in [[1c-settings-testing]] work unchanged; test the wiring with `moto`.
- **Env vars first,** so a deploy can override one value.
- **One source per field.** A sub-model may span both (`db/auth/method` in Parameter Store, `db--auth--password` in Secrets Manager).
- **Names match field names, case-sensitively.** `extra="forbid"` catches wrong names inside a sub-model; a wrong first segment (`/shop/prd/Db/host`) is silently ignored.
- **Lists are JSON strings.**
- **Few calls per startup:** one secret, one small path (a `GetParametersByPath` call per 10 parameters). Every new instance repeats them, and Parameter Store allows 40 TPS per account by default.
- **Least privilege:** `GetSecretValue` on the app's secret ARN (`-??????` suffix, not `-*`), `GetParametersByPath` on its path.

## Anti-patterns
- **Secrets in env vars,** including `{{resolve:secretsmanager:...}}`: plain text in the deployment configuration.
- **Rebuilding settings often with these sources.** Each rebuild is AWS calls ([[4a-settings-refreshing-values-ttl]]).
- **An `env_prefix` added later.** The sources inherit it; pass `env_prefix=""` to them.
- **No route to AWS from a VPC.** Every startup fails on the connect timeout; add a NAT gateway or interface endpoints.

## Related
- [[1a-settings-management]]
- [[1c-settings-testing]]
- [[4a-settings-refreshing-values]]
