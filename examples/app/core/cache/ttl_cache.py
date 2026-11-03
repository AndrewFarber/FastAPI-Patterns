import logging
import time
from collections.abc import Callable
from datetime import timedelta

logger = logging.getLogger(__name__)


class TtlCache:
    def __init__(
        self,
        fetch: Callable[[str], str],
        ttl: timedelta,
        retry: timedelta = timedelta(seconds=30),
    ) -> None:
        self._fetch = fetch
        self._ttl = ttl.total_seconds()
        self._retry = min(retry, ttl).total_seconds()
        self._values: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> str:
        cached = self._values.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            value, ttl = self._fetch(key), self._ttl
        except Exception:
            if cached is None:
                raise
            logger.warning(
                "refresh of %s failed; serving the last good value",
                key,
                exc_info=True,
            )
            value, ttl = cached[1], self._retry
        self._values[key] = (time.monotonic() + ttl, value)
        return value

    def invalidate(self, key: str) -> None:
        cached = self._values.get(key)
        if cached:
            self._values[key] = (0.0, cached[1])
