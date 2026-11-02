from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.clients.runtime_flags import AppConfigFlags, RuntimeFlags
from app.config.settings import get_settings


@lru_cache
def get_appconfig_flags() -> AppConfigFlags | None:
    """One client per process (on Lambda: per execution environment), like get_settings()."""
    source = get_settings().features.runtime_flags
    return AppConfigFlags(source.application, source.environment, source.profile) if source else None


def get_runtime_flags() -> RuntimeFlags:
    client = get_appconfig_flags()
    return client.get() if client else RuntimeFlags()        # no AppConfig configured: safe defaults


RuntimeFlagsDep = Annotated[RuntimeFlags, Depends(get_runtime_flags)]
