import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.log import configure_logging
from app.config.settings import get_settings
from app.db.engine import build_engine
from app.dependencies.settings import SettingsDep

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Runs once per process at startup, not per request
    settings = get_settings()
    app.state.engine = build_engine(settings.db, application_name=settings.app.name)
    yield
    app.state.engine.dispose()        # on shutdown


def create_app() -> FastAPI:
    settings = get_settings()         # validates now: bad config fails startup, not the first request
    configure_logging(settings.log)
    logger.info("settings loaded: %s", settings.model_dump_json())   # SecretStr values print as **********

    app = FastAPI(title=settings.app.name, debug=settings.app.debug, lifespan=lifespan)
    # CORS is set here only: a gateway's CORS config would override these headers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allow_origins,
        allow_methods=settings.cors.allow_methods,
        allow_headers=settings.cors.allow_headers,
        allow_credentials=settings.cors.allow_credentials,
    )

    @app.get("/healthz")              # readiness probe: no DB query
    def healthz(settings: SettingsDep) -> dict[str, str]:
        return {"status": "ok", "app": settings.app.name}

    return app


app = create_app()                    # module import builds and validates settings
