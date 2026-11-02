---
title: "Accessing settings"
category: project-structure
tags: [settings, dependencies, fastapi]
status: draft
related: ["[[1a-settings-management]]", "[[1c-settings-testing]]", "[[1e-settings-lambda]]", "[[4a-settings-refreshing-values]]"]
---

# Accessing settings

## Problem
`Settings` has to be created once, validated before the app serves traffic, reachable from routes and from code outside requests, and replaceable in tests. How it's created decides how easy each of those is.

## Use when
- Wiring the `Settings` class from [[1a-settings-management]] into an app.

## Avoid when
- Never; pick one of the three approaches below and use only that one.

## Solution

### 1. Module singleton
```python
# app/config/settings.py (fragment)
settings = Settings()
```
```python
# anywhere
from app.config.settings import settings

engine = create_engine(str(settings.db.url))
```
- **Pros:** simplest; usable anywhere, including outside requests.
- **Cons:** built at import time, so importing anything that imports settings needs a valid environment; tests must set env vars before import or patch the object.

### 2. Cached function + `Depends` (recommended default, used by the example)
```python
# app/config/settings.py (fragment)
from functools import lru_cache


@lru_cache
def get_settings() -> Settings:
    return Settings()
```
```python
# app/dependencies/settings.py
from typing import Annotated

from fastapi import Depends

from app.config.settings import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]
```
`main.py` calls `get_settings()` once at import, so bad config fails at startup (on Lambda: during init, [[1e-settings-lambda]]) instead of on the first request. It logs the result, sets up logging, CORS, and the DB engine, and serves the readiness route through `SettingsDep`:

```python
# app/main.py
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.log import configure_logging
from app.config.settings import get_settings
from app.db.engine import build_engine
from app.dependencies.settings import SettingsDep
from app.observability import DeploymentFilter

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # On Lambda this runs once per execution environment, during init, not per request
    settings = get_settings()
    app.state.engine = build_engine(settings.db, application_name=settings.app.name)
    yield
    app.state.engine.dispose()        # on SIGTERM, when Lambda shuts the environment down


def create_app() -> FastAPI:
    settings = get_settings()         # validates now: bad config fails init, so the version never takes traffic
    configure_logging(settings.log, DeploymentFilter(settings.app))
    logger.info("settings loaded: %s", settings.model_dump_json())   # SecretStr values print as **********

    app = FastAPI(title=settings.app.name, debug=settings.app.debug, lifespan=lifespan)
    # CORS is set here only: a Function URL CORS config would replace these headers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allow_origins,
        allow_methods=settings.cors.allow_methods,
        allow_headers=settings.cors.allow_headers,
        allow_credentials=settings.cors.allow_credentials,
    )

    @app.get("/healthz")              # AWS_LWA_READINESS_CHECK_PATH
    def healthz(settings: SettingsDep) -> dict[str, str | None]:
        return {"status": "ok", "version": settings.app.version}

    return app


app = create_app()                    # module import = Lambda init phase
```
- **Pros:** built once and cached; routes declare the dependency explicitly.
- **Cons:** non-request code (lifespan, scripts, tasks) calls `get_settings()` directly.
- **Testing:** set env vars and call `get_settings.cache_clear()` ([[1c-settings-testing]]). `dependency_overrides` alone misses code that calls `get_settings()` directly, like `create_app()` and the lifespan above.
- Follows the layout rule: `config/` creates settings, `dependencies/` hands them to requests.

### 3. Built in the app factory
```python
# main.py (fragment)
def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:                # not `settings or ...`: never rely on a model's truthiness
        settings = Settings()
    logger.info("settings loaded: %s", settings.model_dump_json())
    app = FastAPI(title=settings.app.name, debug=settings.app.debug)
    app.state.settings = settings
    app.include_router(health.router)
    return app


app = create_app()
```
```python
# dependencies/settings.py (fragment)
def get_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings)]
```
- **Pros:** most explicit; each app instance has its own settings, so tests just call `create_app(Settings(...))`.
- **Cons:** requires an app factory; code outside requests needs the app (or the settings) passed in.

### Choosing

| | Singleton | Cached function | App factory |
|---|---|---|---|
| Setup cost | Lowest | Low | Medium |
| Created | At import | First call (call it at startup) | At app creation |
| Test override | Env vars before import | Env vars + `cache_clear()` | Pass to `create_app()` |
| Outside requests | Import it | Call `get_settings()` | Pass it in |
| Best for | Scripts, tiny apps | Most apps | Apps already using a factory |

## Pitfalls
- **Validating on the first request.** A lazily created `Settings` lets a misconfigured version finish startup and pass the readiness check (LWA on Lambda), so the error only shows on the first request. Build it at import.
- **Mixing approaches.** A factory that stores `app.state.settings` while `SettingsDep` calls the cached `get_settings()` gives routes the environment's settings, not the ones passed in. One approach per app.
- **Relying on `dependency_overrides` for settings.** It only reaches request-time `Depends()`, not startup code.
- **Logging `model_dump()` of a model with plain `str` secrets.** Only `SecretStr` is masked.

## Related
- [[1a-settings-management]]
- [[1c-settings-testing]]
- [[1e-settings-lambda]]
- [[4a-settings-refreshing-values]]
