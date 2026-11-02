---
title: "Caching live values from AWS"
category: project-structure
tags: [settings, caching, aws, secrets-manager, parameter-store]
status: draft
related: ["[[4a-settings-refreshing-values]]", "[[2b-settings-db-rotated-password]]", "[[3b-settings-aws-sources]]"]
---

# Caching live values from AWS

Settings hold only *where* and *how often* to fetch; a `TtlCache` (`core/cache/`) around an AWS client (`core/aws/`) fetches the live value. One fetch per expired key, the old value while it refreshes, and the last good value with a backoff when the source is down.

## Fits when
- Individual secrets or parameters change while the app runs and are read per request or per connection.

Not when:
- A redeploy is acceptable, or the value is read once at startup ([[3b-settings-aws-sources]]).

## Signals
- **Feature:** "cache the secret", "don't call Secrets Manager on every request", rotated values.
- **Code:** `get_secret_value` / `get_parameter` per request; `functools.lru_cache` on a fetch (never expires); a hand-rolled `dict` cache without a lock; boto3 clients with default timeouts on the request path.

## Pattern
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

## Rules
- **Settings stay immutable;** the cache is a client built at startup.
- **Stampede protection:** a per-key lock; other threads get the old value at once and wait only when there is none.
- **Last good value on errors,** with one warning and a `retry_seconds` backoff; raise only when there has never been a value.
- **`invalidate()` keeps the fallback** and forces the next read to fetch ([[2b-settings-db-rotated-password]]).
- **Short boto3 timeouts on the request path** (1 s connect, 2 s read, 2 attempts).
- **TTLs in minutes for secrets.** Each fetch is a billed, throttled API call, once per process.

## Anti-patterns
- **No backoff.** During an outage every request waits for the timeout.
- **Stale forever without alerting.** "Last good value" hides a permanent outage; alert on the warning.

## Related
- [[4a-settings-refreshing-values]]
- [[2b-settings-db-rotated-password]]
- [[3b-settings-aws-sources]]
