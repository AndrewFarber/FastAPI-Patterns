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
