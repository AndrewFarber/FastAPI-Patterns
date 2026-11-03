---
title: "Accessing settings"
category: project-structure
related:
  - "[[settings-guide]]"
  - "[[layout-core]]"
  - "[[settings-management]]"
  - "[[settings-feature-flags]]"
  - "[[settings-testing]]"
---

# Accessing settings

## Overview
Build `Settings` once, at startup, through a cached `get_settings()`, and hand it to routes with `SettingsDep`. Only entry points read `Settings`; everything below them receives the sub-model it needs. Bad config fails startup instead of the first request.

## Rules
- **Validate at import.** `app = create_app()` at module level builds settings before uvicorn listens.
- **Startup objects in the lifespan.** The engine is built on startup and disposed on shutdown; nothing reads settings per request to rebuild it.
- **`core/config/` creates, `core/dependencies/` hands out** ([[layout-core]]).
- **Only entry points read `Settings`.** Routes, `create_app()`, the lifespan, and workers; use cases, repositories, and domain code get sub-models as arguments.
- **Keep the readiness route trivial.** `/healthz` checks no dependency; a DB query there would fail every new instance on a database blip.

## Code example
`get_settings()` is `lru_cache`d next to `Settings` ([[settings-management]]); `core/dependencies/` turns it into `SettingsDep`:

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
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.aws.values import create_parameter_store_cache
from app.core.config.settings import get_settings
from app.core.db.engine import create_engine
from app.core.dependencies.settings import SettingsDep
from app.core.errors import handlers as error_handlers
from app.core.messaging.sns import create_sns_sender
from app.core.observability.log import configure_logging
from app.core.outbox.relay import OutboxRelay
from app.services.orders.api.router import router as orders_router
from app.services.users.api.router import router as users_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    app.state.engine = create_engine(
        settings.db, application_name=settings.app.name
    )
    app.state.relay = OutboxRelay(
        app.state.engine,
        create_sns_sender(settings.events),
        settings.events.sweep_batch_size,
    )
    app.state.parameters = create_parameter_store_cache(
        settings.switches.region,
        timedelta(seconds=settings.switches.ttl_seconds),
    )
    # A missing parameter fails startup, not every order
    app.state.parameters.get(settings.switches.orders_paused)
    yield
    app.state.engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log)
    logger.info("settings loaded: %s", settings.model_dump_json())

    app = FastAPI(
        title=settings.app.name, debug=settings.app.debug, lifespan=lifespan
    )
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

Entry points read settings: routes through `SettingsDep`, and `create_app()`, the lifespan, and other process entry points (`workers.py`, scripts) by calling `get_settings()`. They pass sub-models down: a use case that needs flags takes `FeaturesSettings` ([[settings-feature-flags]]), `create_engine()` takes `DbSettings`. Tests set env vars and call `get_settings.cache_clear()` ([[settings-testing]]).
