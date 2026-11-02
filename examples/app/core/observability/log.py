import logging
import sys

from app.core.config.log import LogSettings


def configure_logging(log: LogSettings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(levelname)s %(name)s: %(message)s")
    )
    logging.basicConfig(level=log.level, handlers=[handler], force=True)
