---
title: "Refreshing settings values"
category: project-structure
related:
  - "[[settings-guide]]"
---

# Refreshing settings values

## Overview
`Settings` stays frozen and is built once. A redeploy is the default way to change a value; a value that can't wait for one is read through a `TtlCache` (`core/cache/`) around an AWS client (`core/aws/`), and settings hold only *where* and *how often* to fetch it. One fetch per expired key, the old value while it refreshes, and the last good value with a backoff when the source is down.

## Rules
- **Never mutate or rebuild settings.** Startup objects (engine, middleware, mounted routers) would keep the old values, and a failed rebuild would fail every request; the cache is a client built at startup.
- **Stampede protection:** a per-key lock; other threads get the old value at once and wait only when there is none.
- **Last good value on errors,** with one warning and a `retry_seconds` backoff; raise only when there has never been a value.
- **`invalidate()` keeps the fallback** and forces the next read to fetch, for a caller that knows the value is stale.
- **Short boto3 timeouts on the request path** (1 s connect, 2 s read, 2 attempts).
- **TTLs in minutes for secrets.** Each fetch is a billed, throttled API call, once per process.
- **Caches live per process;** each new instance reads fresh values anyway.
- **Runtime changes reach every running version at once,** unlike a deploy, which can be rolled out gradually and rolled back.

## Code example
```python
# app/core/cache/ttl_cache.py
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
```

```python
# app/core/aws/values.py
import boto3
from botocore.config import Config

from app.core.cache.ttl_cache import TtlCache

CLIENT_CONFIG = Config(connect_timeout=1, read_timeout=2, retries={"mode": "standard", "max_attempts": 2})


def secrets_manager_cache(region: str, ttl_seconds: float) -> TtlCache:
    client = boto3.client("secretsmanager", region_name=region, config=CLIENT_CONFIG)
    return TtlCache(lambda secret_id: client.get_secret_value(SecretId=secret_id)["SecretString"], ttl_seconds)


def parameter_store_cache(region: str, ttl_seconds: float) -> TtlCache:
    client = boto3.client("ssm", region_name=region, config=CLIENT_CONFIG)
    return TtlCache(lambda name: client.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"], ttl_seconds)
```

An entry point builds the cache once at startup, from a sub-model that names the secret or parameter and its TTL, and passes it to whatever reads the value.
