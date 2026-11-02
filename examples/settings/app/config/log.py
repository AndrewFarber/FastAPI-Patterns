import logging
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LogSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


def configure_logging(log: LogSettings) -> None:
    """Send every logger's records to stdout at the configured level."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=log.level, handlers=[handler], force=True)   # force: replace earlier handlers
