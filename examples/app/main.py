import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config.log import configure_logging
from app.core.config.settings import get_settings
from app.core.db.engine import build_engine
from app.core.dependencies.settings import SettingsDep
from app.core.exceptions import handlers as error_handlers
from app.core.messaging.sns import build_sns_sender
from app.core.outbox.relay import OutboxRelay
from app.services.orders.api.router import router as orders_router
from app.services.users.api.router import router as users_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    app.state.engine = build_engine(settings.db, application_name=settings.app.name)
    app.state.relay = OutboxRelay(app.state.engine, build_sns_sender(settings.events), settings.events.sweep_batch_size)
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
