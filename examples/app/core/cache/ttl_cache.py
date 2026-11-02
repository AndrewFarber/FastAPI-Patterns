import logging
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class TtlCache:
    def __init__(self, fetch: Callable[[str], str], ttl_seconds: float, retry_seconds: float = 30) -> None:
        self._fetch = fetch
        self._ttl = ttl_seconds
        self._retry = min(retry_seconds, ttl_seconds)
        self._values: dict[str, tuple[float, str]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def get(self, key: str) -> str:
        cached = self._values.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        lock = self._lock_for(key)
        if cached is None:
            lock.acquire()
        elif not lock.acquire(blocking=False):
            return cached[1]
        try:
            cached = self._values.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            try:
                value = self._fetch(key)
            except Exception:
                if cached is None:
                    raise
                self._values[key] = (time.monotonic() + self._retry, cached[1])
                logger.warning("refresh of %s failed; serving the last good value", key, exc_info=True)
                return cached[1]
            self._values[key] = (time.monotonic() + self._ttl, value)
            return value
        finally:
            lock.release()

    def invalidate(self, key: str) -> None:
        cached = self._values.get(key)
        if cached:
            self._values[key] = (0.0, cached[1])

    def _lock_for(self, key: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(key, threading.Lock())
