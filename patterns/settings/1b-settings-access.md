---
title: "Accessing settings"
category: project-structure
tags: [settings, dependencies, fastapi]
status: draft
related: ["[[1a-settings-management]]", "[[1c-settings-testing]]", "[[4a-settings-refreshing-values]]"]
---

# Accessing settings

Build `Settings` once, at startup, and hand it out through exactly one access approach. Bad config then fails startup instead of the first request.

## Fits when
- Wiring the `Settings` class from [[1a-settings-management]] into an app.

Not when:
- Never; pick one of the three approaches and use only that one.

## Signals
- **Feature:** a route, service, or task needs a setting; "create the app"; adding a lifespan.
- **Code:** `Settings()` inside a route, middleware, or service; `settings = Settings()` at module level *and* `app.state.settings`; `dependency_overrides[get_settings]` in tests; a readiness route that queries the DB.

## Pattern

### 1. Module singleton
```python
# app/core/config/settings.py (fragment)
settings = Settings()
```
Simplest and usable anywhere, but built at import: anything importing it needs a valid environment, and tests must set env vars before import. For scripts and tiny apps.

### 2. Cached function + `Depends` (default, used by the example)
```python
# app/core/dependencies/settings.py
from typing import Annotated

from fastapi import Depends

from app.core.config.settings import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]
```

`create_app()` calls `get_settings()` at import, so validation runs at startup. It logs the result (`SecretStr` prints as `**********`), configures logging and CORS, and the lifespan builds the DB engine once:

```python
# app/main.py
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config.log import configure_logging
from app.core.config.settings import get_settings
from app.core.db.engine import build_engine
from app.core.dependencies.settings import SettingsDep
from app.core.events.bus import EventBus
from app.core.exceptions import handlers as error_handlers
from app.services.orders import event_handlers as orders_handlers
from app.services.orders.api.router import router as orders_router
from app.services.users.api.router import router as users_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    app.state.engine = build_engine(settings.db, application_name=settings.app.name)
    app.state.bus = EventBus(app.state.engine)
    orders_handlers.register(app.state.bus)
    yield
    app.state.engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log)
    logger.info("settings loaded: %s", settings.model_dump_json())

    app = FastAPI(title=settings.app.name, debug=settings.app.debug, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allow_origins,
        allow_methods=settings.cors.allow_methods,
        allow_headers=settings.cors.allow_headers,
        allow_credentials=settings.cors.allow_credentials,
    )

    error_handlers.register(app)
    app.include_router(users_router)
    app.include_router(orders_router)

    @app.get("/healthz")
    def healthz(settings: SettingsDep) -> dict[str, str]:
        return {"status": "ok", "app": settings.app.name}

    return app


app = create_app()
```

Non-request code (lifespan, scripts, tasks) calls `get_settings()` directly. Tests set env vars and call `get_settings.cache_clear()` ([[1c-settings-testing]]).

### 3. Built in the app factory
```python
# main.py (fragment)
def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    app = FastAPI(title=settings.app.name, debug=settings.app.debug)
    app.state.settings = settings
    return app
```
```python
# dependencies/settings.py (fragment)
def get_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings)]
```
Most explicit: tests call `create_app(Settings(...))`. Code outside requests needs the settings passed in.

| | Singleton | Cached function | App factory |
|---|---|---|---|
| Test override | Env vars before import | Env vars + `cache_clear()` | Pass to `create_app()` |
| Outside requests | Import it | Call `get_settings()` | Pass it in |
| Best for | Scripts, tiny apps | Most apps | Apps already using a factory |

## Rules
- **Validate at import.** `app = create_app()` at module level builds settings before uvicorn listens.
- **Startup objects in the lifespan.** The engine is built on startup and disposed on shutdown; nothing reads settings per request to rebuild it.
- **`core/config/` creates, `core/dependencies/` hands out** ([[1b-layout-core]]).
- **Keep the readiness route trivial.** `/healthz` returns a constant; a DB query there would fail every new instance on a database blip.

## Anti-patterns
- **Lazy settings.** Startup and the readiness check pass, and the error shows only on the first request.
- **Mixing approaches.** A factory storing `app.state.settings` while `SettingsDep` calls the cached `get_settings()` gives routes the environment's settings, not the ones passed in.
- **`dependency_overrides` for settings.** It only reaches request-time `Depends()`, not `create_app()` or the lifespan.

## Related
- [[1a-settings-management]]
- [[1c-settings-testing]]
- [[4a-settings-refreshing-values]]
