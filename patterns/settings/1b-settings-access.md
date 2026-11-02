---
title: "Accessing settings"
category: project-structure
tags: [settings, dependencies, fastapi]
status: draft
related: ["[[1a-settings-management]]", "[[1c-settings-testing]]", "[[2f-settings-feature-flags]]", "[[4a-settings-refreshing-values]]"]
---

# Accessing settings

Build `Settings` once, at startup, through a cached `get_settings()`, and hand it to routes with `SettingsDep`. Only entry points read `Settings`; everything below them receives the sub-model it needs. Bad config fails startup instead of the first request.

## Fits when
- Wiring the `Settings` class from [[1a-settings-management]] into an app.

Not when:
- Never.

## Signals
- **Feature:** a route, service, or task needs a setting; "create the app"; adding a lifespan.
- **Code:** `Settings()` inside a route, middleware, or service; `settings = Settings()` at module level; `app.state.settings`; `get_settings()` called in a use case or repository; `dependency_overrides[get_settings]` in tests; a readiness route that queries the DB.

## Pattern
`get_settings()` is `lru_cache`d next to `Settings` ([[1a-settings-management]]); `core/dependencies/` turns it into `SettingsDep`:

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

Entry points read settings: routes through `SettingsDep`, and `create_app()`, the lifespan, and other process entry points (workers, scripts) by calling `get_settings()`. They pass sub-models down: a use case that needs flags takes `FeatureSettings` ([[2f-settings-feature-flags]]), `build_engine()` takes `DbSettings`. Tests set env vars and call `get_settings.cache_clear()` ([[1c-settings-testing]]).

## Rules
- **Validate at import.** `app = create_app()` at module level builds settings before uvicorn listens.
- **Startup objects in the lifespan.** The engine is built on startup and disposed on shutdown; nothing reads settings per request to rebuild it.
- **`core/config/` creates, `core/dependencies/` hands out** ([[1b-layout-core]]).
- **Only entry points read `Settings`.** Routes, `create_app()`, the lifespan, and workers; use cases, repositories, and domain code get sub-models as arguments.
- **Keep the readiness route trivial.** `/healthz` returns a constant; a DB query there would fail every new instance on a database blip.

## Anti-patterns
- **Lazy settings.** Startup and the readiness check pass, and the error shows only on the first request.
- **A second access path.** A module-level `settings = Settings()` or `app.state.settings` next to `get_settings()` gives tests and code two copies that can disagree.
- **`get_settings()` deep in the code.** A use case that reads global settings hides what it depends on, and its tests need the environment instead of a sub-model.
- **`dependency_overrides` for settings.** It only reaches request-time `Depends()`, not `create_app()` or the lifespan.

## Related
- [[1a-settings-management]]
- [[1c-settings-testing]]
- [[2f-settings-feature-flags]]
- [[4a-settings-refreshing-values]]
