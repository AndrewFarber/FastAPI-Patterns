---
title: "pydantic-settings AWS sources"
category: project-structure
tags: [settings, aws, secrets-manager, parameter-store, pydantic-settings]
status: draft
related: ["[[3b-settings-aws-sources]]", "[[1e-settings-lambda]]", "[[1d-settings-deployments-shared-config]]", "[[4a-settings-refreshing-values-ttl]]"]
---

# pydantic-settings AWS sources

## Problem
Lambda can't inject secrets into env vars, and env vars hold only 4 KB ([[3b-settings-aws-sources]], [[1e-settings-lambda]]). The app has to read Secrets Manager and Parameter Store itself, without bypassing the validation in `Settings`.

## Use when
- Secrets the app needs at startup, or more configuration than fits in the function's env vars.

## Avoid when
- A few non-secret values: set them as env vars at deploy time ([[3b-settings-aws-sources]]); no AWS calls at init.
- Values must change while the app runs. These sources load once per execution environment, at init; see [[4a-settings-refreshing-values]].

## Solution
Add pydantic-settings' built-in AWS sources. They run when `Settings()` is built, at init on Lambda, and values pass through the same validation as env vars.

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
    SettingsConfigDict,
)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="forbid",
        frozen=True,
    )

    # ... sub-model fields as in 1a-settings-management ...

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
# The function's env vars; unset locally
AWS_SECRETS_MANAGER_SECRET_ID=orders/prd/app
AWS_SSM_PATH=/orders/prd
# The sources build their own boto3 clients: standard retries, 1.1 s connect timeout
AWS_DEFAULTS_MODE=in-region
# Region and credentials come from Lambda (AWS_REGION, the execution role)
```

### What goes where
| | Secrets Manager | Parameter Store |
|---|---|---|
| Holds | Secrets: DB password, API keys | Plain configuration: hosts, pool sizes, client IDs |
| Shape | One secret, JSON object | One parameter per field, under a path |
| Nested field | Key `db--auth--password` | Name `/orders/prd/db/host` |
| Example | `{"db--auth--password": "...", "email--password": "..."}` | `/orders/prd/db/pool_size` = `1` |

- **One source per field.** A field defined in both is confusing to debug; Secrets Manager wins because it's listed first.
- **A sub-model can span both sources:** `/orders/prd/db/auth/method` = `password` in Parameter Store and `db--auth--password` in Secrets Manager are merged into one `PasswordAuth`.
- **Names are case-sensitive and must match field names.** Inside a sub-model, `extra="forbid"` rejects `/orders/prd/db/Host` and `db/pool_szie`. A wrong first segment is silently ignored, as with env vars: `/orders/prd/Db/host` or `emial/host` never reaches `Settings`, and `email` stays disabled.
- **Lists are JSON strings:** `/orders/prd/auth/audiences` = `["1example23456789"]`. Secrets Manager keys can't express arrays (`x--0`), but a JSON string value works.
- **`SecureString` parameters are decrypted** automatically.
- **Paths per environment:** `/orders/prd/...`, `/orders/stg/...`; secret IDs `orders/prd/app`. The deployment picks one with `AWS_SSM_PATH` and `AWS_SECRETS_MANAGER_SECRET_ID`.

### IAM permissions
The function's execution role needs read access to exactly its own secret and path:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:orders/prd/app-??????"
    },
    {
      "Effect": "Allow",
      "Action": "ssm:GetParametersByPath",
      "Resource": [
        "arn:aws:ssm:us-east-1:123456789012:parameter/orders/prd",
        "arn:aws:ssm:us-east-1:123456789012:parameter/orders/prd/*"
      ]
    }
  ]
}
```

- `-??????` matches the six random characters AWS appends to secret ARNs. `-*` would also match `orders/prd/app-admin`.
- Add `kms:Decrypt` on the key only when the secret or `SecureString` uses a customer managed KMS key.

### On Lambda
Each new execution environment builds `Settings` at init and reads AWS again ([[1e-settings-lambda]]):
- **Calls per cold start:** one `GetSecretValue`, plus one `GetParametersByPath` per 10 parameters (the page size). 30 parameters is 4 calls.
- **Parameter Store throughput:** 40 TPS by default per account and Region, shared by `GetParameter`, `GetParameters` and `GetParametersByPath` across all apps. A burst of 50 cold starts with 30 parameters each is 150 calls; throttled ones retry and can fail init. Keep the path small (non-secret values can be env vars set at deploy, [[3b-settings-aws-sources]]), or enable higher throughput (charged).
- **Init budget:** init has 10 s. `AWS_DEFAULTS_MODE=in-region` limits each connect attempt to 1.1 s with three attempts, so an unreachable endpoint fails init with a clear error instead of an init timeout.
- **SnapStart** doesn't apply to container images, so values are read fresh by each environment.

### Testing
Tests leave `AWS_SECRETS_MANAGER_SECRET_ID` and `AWS_SSM_PATH` unset, so no AWS source is added and the fixtures in [[1c-settings-testing]] work unchanged. To test the AWS wiring itself, use `moto` (`with mock_aws():`) to create the secret and parameters, then build `Settings()`.

## Pitfalls
- **Adding an `env_prefix` later.** Both sources inherit it: with `env_prefix="APP_"` they expect keys like `APP_db--auth--password`. Pass `env_prefix=""` to the sources to keep plain keys.
- **Old pydantic-settings versions.** `AWSSystemsManagerSettingsSource` is recent (tested with 2.16), and older versions' Secrets Manager source also needs type-stub packages. Pin a current version.
- **Reading AWS on every settings rebuild.** Each `Settings()` call makes AWS API calls. Fine once per execution environment; with a short TTL ([[4a-settings-refreshing-values-ttl]]) it adds latency, cost, and throttling risk.
- **A missing secret or path fails init.** That's the intent: the new version never takes traffic. Deploy the secret before the app, and check the ID and region first when it happens. A missing path is different: `GetParametersByPath` returns nothing, and the required fields fail validation.
- **No route to the AWS APIs.** A function in a VPC reaches Secrets Manager and Parameter Store only through a NAT gateway or interface VPC endpoints; without either, every init fails on the connect timeout.
- **Different separators.** Env vars use `__`, Secrets Manager keys `--`, Parameter Store `/`. Each maps to the same nested field.
- **Changing shared paths during a deployment.** The old and new versions read the same path and secret while CodeDeploy shifts traffic; add and remove values in the order described in [[1d-settings-deployments-shared-config]].
- **Over-broad IAM.** `secretsmanager:GetSecretValue` on `*` lets the app read every secret in the account. Scope it to the app's own ARNs.

## Related
- [[3b-settings-aws-sources]]
- [[1e-settings-lambda]]
- [[1d-settings-deployments-shared-config]]
- [[4a-settings-refreshing-values-ttl]]
