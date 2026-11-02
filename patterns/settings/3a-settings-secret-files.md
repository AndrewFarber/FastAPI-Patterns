---
title: "Secrets mounted as files"
category: project-structure
tags: [settings, secrets, docker-compose, local-development]
status: draft
related: ["[[1a-settings-management]]", "[[1e-settings-lambda]]", "[[3b-settings-aws-sources]]"]
---

# Secrets mounted as files

## Problem
Running the image locally with docker-compose needs a dev database password. As a plain env var it sits in `compose.yaml` and shows up in `docker inspect`; compose `secrets:` mount it as a file instead. Lambda has no file-mounted secrets, so the same `Settings` must read files locally and ignore them when deployed. pydantic-settings' default secrets source also only reads top-level fields, so secrets for nested sub-models are silently ignored.

## Use when
- Running the app's image locally with docker-compose, against a local database, with no AWS access.

## Avoid when
- Deployed on Lambda: there is nothing to mount, the image's filesystem is read-only apart from `/tmp` ([[1e-settings-lambda]]), and the app reads Secrets Manager itself ([[3b-settings-aws-sources-pydantic]]).
- Plain env vars from a shell or `.env` file are good enough for the dev password.

## Solution
Add the files source only when `SECRETS_DIR` is set, like the AWS sources in [[3b-settings-aws-sources-pydantic]]. Compose sets it; Lambda and tests don't.

```python
# config/settings.py (fragment)
import os

from pydantic_settings import NestedSecretsSettingsSource, PydanticBaseSettingsSource


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
        sources = [init_settings, env_settings]
        # Only when configured: set by docker-compose, unset on Lambda
        if secrets_dir := os.environ.get("SECRETS_DIR"):
            # file db__auth__password -> settings.db.auth.password; a wrong path fails startup
            sources.append(
                NestedSecretsSettingsSource(file_secret_settings, secrets_dir=secrets_dir, secrets_dir_missing="error")
            )
        return tuple(sources)
```

```yaml
# compose.yaml (fragment)
services:
  api:
    image: orders-api:dev
    # The image's CMD listens on 127.0.0.1 for the Lambda Web Adapter; listen on all interfaces here
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
    ports: ["8080:8080"]
    environment:
      SECRETS_DIR: /run/secrets
      DB__HOST: db
      DB__AUTH__METHOD: password
    secrets:
      - source: db_password
        target: db__auth__password          # -> /run/secrets/db__auth__password

secrets:
  db_password:
    file: ./secrets/db_password.txt         # git-ignored
```

- **File names match env var names:** `/run/secrets/db__auth__password` fills `settings.db.auth.password`.
- **Env vars win** over files, so a single value can still be overridden.
- **Deployed, the same code adds no files source**: `SECRETS_DIR` is not in the function's env vars.

## Pitfalls
- **Using the default secrets source.** It skips nested fields without any error; use `NestedSecretsSettingsSource`.
- **The default `secrets_dir_missing="warn"`.** A mistyped path only logs a warning and every secret is missing; `"error"` fails startup instead.
- **Baking secrets into the image** to read them as files on Lambda. Anyone who can pull the image from ECR can read them.
- **Writing secrets to `/tmp`** at init so this source can read them. It adds a copy on disk for nothing; the AWS sources put the values straight into `Settings`.

## Related
- [[1a-settings-management]]
- [[1e-settings-lambda]]
- [[3b-settings-aws-sources]]
