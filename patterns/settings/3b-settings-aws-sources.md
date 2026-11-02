---
title: "Settings from AWS sources"
category: project-structure
tags: [settings, aws, secrets-manager, parameter-store, pydantic-settings]
status: draft
related: ["[[1a-settings-management]]", "[[1c-settings-testing]]", "[[3a-settings-secret-files]]", "[[4a-settings-refreshing-values]]"]
---

# Settings from AWS sources

Read Secrets Manager and Parameter Store as pydantic-settings sources, added only when their env var is set. Values pass through the same validation as env vars, at startup, and local runs and tests need no AWS access.

## Fits when
- Secrets the app needs at startup, or more configuration than fits in env vars (4 KB on Lambda).

Not when:
- A few non-secret values: plain env vars set at deploy time, no AWS calls at startup.
- Values change while the app runs: these load once per process ([[4a-settings-refreshing-values]]).
- Local development and tests: env vars or [[3a-settings-secret-files]].

## Signals
- **Feature:** "read the secret from Secrets Manager", "too many env vars", "config in Parameter Store"; adding, removing, or renaming a value there while a canary or rollback can run two versions.
- **Code:** ad hoc `boto3` `get_secret_value` / `get_parameter` calls that fill settings by hand; secrets in deploy-time env vars or `{{resolve:secretsmanager:...}}`; a startup script that exports parameters as env vars; a PR that adds a required field and its shared value together.

## Pattern
```bash
uv add "pydantic-settings[aws-secrets-manager,aws-systems-manager]"
```

```python
# app/config/settings.py (fragment)
import os

from pydantic_settings import (
    AWSSecretsManagerSettingsSource,
    AWSSystemsManagerSettingsSource,
    BaseSettings,
    PydanticBaseSettingsSource,
)


class Settings(BaseSettings):
    # model_config and fields as in 1a-settings-management

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # First source wins: env vars still override AWS, so a single value can be patched in a deploy
        sources = [init_settings, env_settings]

        # Only when configured: local runs and tests need no AWS access
        if secret_id := os.environ.get("AWS_SECRETS_MANAGER_SECRET_ID"):
            sources.append(AWSSecretsManagerSettingsSource(settings_cls, secret_id))
        if ssm_path := os.environ.get("AWS_SSM_PATH"):
            sources.append(AWSSystemsManagerSettingsSource(settings_cls, ssm_path))

        return tuple(sources)
```

```bash
# Deployed env vars; unset locally
AWS_SECRETS_MANAGER_SECRET_ID=orders/prd/app
AWS_SSM_PATH=/orders/prd
# The sources build their own boto3 clients: short connect timeout, standard retries
AWS_DEFAULTS_MODE=in-region
```

| | Secrets Manager | Parameter Store |
|---|---|---|
| Holds | Secrets | Plain configuration |
| Shape | One secret, a JSON object | One parameter per field under a path |
| Nested field | Key `db--auth--password` | `/orders/prd/db/host` |

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
- **Names match field names, case-sensitively.** `extra="forbid"` catches wrong names inside a sub-model; a wrong first segment (`/orders/prd/Db/host`) is silently ignored.
- **Lists are JSON strings.**
- **Few calls per startup:** one secret, one small path (a `GetParametersByPath` call per 10 parameters). Every new Lambda instance repeats them, and Parameter Store allows 40 TPS per account by default.
- **Least privilege:** `GetSecretValue` on the app's secret ARN (`-??????` suffix, not `-*`), `GetParametersByPath` on its path.
- **Shared values change by expand, then contract.** Old and new versions read the same path and secret, and `extra="forbid"` rejects what a version doesn't know:
    - *Add:* release a version that declares the field with a default → once no older version can get traffic (rollbacks included), add the value → later, optionally drop the default.
    - *Remove:* release a version that stops using the field but still declares it → once no older version can get traffic, delete the value → later, delete the field.
    - *Rename* = add + remove. For large changes, give each release its own path (`AWS_SSM_PATH=/orders/prd/releases/1.4.2`); keep secrets shared.

## Anti-patterns
- **Secrets in env vars,** including `{{resolve:secretsmanager:...}}`: plain text in the function configuration.
- **Rebuilding settings often with these sources.** Each rebuild is AWS calls ([[4a-settings-refreshing-values-ttl]]).
- **An `env_prefix` added later.** The sources inherit it; pass `env_prefix=""` to them.
- **Adding a value before every runnable version accepts it,** or deleting a field and its value in one release. The other version fails its next startup.
- **Relaxing `extra="forbid"` to ease deploys.** Typos are silently ignored again.
- **No route to AWS from a VPC.** Every startup fails on the connect timeout; add a NAT gateway or interface endpoints.

## Related
- [[1a-settings-management]]
- [[1c-settings-testing]]
- [[3a-settings-secret-files]]
- [[4a-settings-refreshing-values]]
