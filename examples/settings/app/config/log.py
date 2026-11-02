import json
import logging
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LogSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_format: bool = False


# Attributes every LogRecord has; anything else was added by a filter or extra={...}
_RECORD_FIELDS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, so CloudWatch Logs Insights can query the fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **{k: v for k, v in vars(record).items() if k not in _RECORD_FIELDS},
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(log: LogSettings, *filters: logging.Filter) -> None:
    """Send every logger's records to stdout (CloudWatch on Lambda) at the configured level."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if log.json_format else logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    for f in filters:
        handler.addFilter(f)          # on the root handler, so records from child loggers get it too
    logging.basicConfig(level=log.level, handlers=[handler], force=True)   # force: replace earlier handlers
