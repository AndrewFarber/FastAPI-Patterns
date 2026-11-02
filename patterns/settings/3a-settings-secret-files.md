---
title: "Secrets mounted as files"
category: project-structure
tags: [settings, secrets, docker-compose, local-development]
status: draft
related: ["[[1a-settings-management]]", "[[3b-settings-aws-sources]]"]
---

# Secrets mounted as files

Add a nested secrets-files source to `Settings` only when `SECRETS_DIR` is set. Locally, docker-compose mounts secrets as files named like env vars; deployed, the same code adds no source.

## Fits when
- Running the image locally with docker-compose, against a local database, without AWS access.

Not when:
- Deployed on Lambda: nothing to mount; the app reads Secrets Manager ([[3b-settings-aws-sources]]).
- Plain env vars from a shell are good enough for the dev password.

## Signals
- **Feature:** "docker-compose for local dev", "keep the dev password out of compose.yaml".
- **Code:** `secrets_dir=` in `SettingsConfigDict` (top-level fields only, nested ones silently skipped); passwords in `compose.yaml` `environment:`; secrets copied to `/tmp` at startup.

## Pattern
```python
# app/config/settings.py (fragment)
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
        # Only when configured: set by docker-compose, unset when deployed
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

## Rules
- **Sources are opt-in by env var,** the same switch style as the AWS sources ([[3b-settings-aws-sources]]); tests and deployed environments get none.
- **File names are env var names,** lower-case with `__`.
- **Env vars win over files,** so one value can still be overridden.
- **`secrets_dir_missing="error"`:** a mistyped path fails startup instead of logging a warning.

## Anti-patterns
- **The default secrets source.** Skips nested fields without an error.
- **Baking secrets into the image** to read as files. Anyone who can pull it reads them.

## Related
- [[1a-settings-management]]
- [[3b-settings-aws-sources]]
