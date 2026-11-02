---
title: "Caching live values from AWS"
category: project-structure
tags: [settings, caching, aws, secrets-manager, parameter-store]
status: draft
related: ["[[4a-settings-refreshing-values]]", "[[1e-settings-lambda]]", "[[2b-settings-db-rotated-password]]", "[[3b-settings-aws-sources]]"]
---

# Caching live values from AWS

## Problem
A few values must stay current while the app runs. Fetching them from AWS on every use is slow and costly; caching them naively lets a burst of requests all refetch at once, and an AWS outage fails every request or makes each one wait for a timeout.

## Use when
- Individual secrets or parameters change while the app runs and are read per request or per connection.

## Avoid when
- A redeploy is acceptable, or the value is read once at init ([[3b-settings-aws-sources]]).

## Solution
Keep `Settings` immutable. It holds only *where* and *how often* to fetch. A cache client in `clients/`, created at startup (at init on Lambda), fetches the live value.

```python
# app/clients/ttl_cache.py
import logging
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class TtlCache:
    """Per-key cache: one fetch per expired key; the last good value while refreshing or when a fetch fails."""

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
            lock.acquire()                            # no value yet: wait for the fetch
        elif not lock.acquire(blocking=False):
            return cached[1]                          # another thread is refreshing: serve the old value
        try:
            cached = self._values.get(key)            # another thread may have refreshed it
            if cached and cached[0] > time.monotonic():
                return cached[1]
            try:
                value = self._fetch(key)
            except Exception:
                if cached is None:
                    raise
                # Back off: the next fetch waits retry_seconds instead of running on every call
                self._values[key] = (time.monotonic() + self._retry, cached[1])
                logger.warning("refresh of %s failed; serving the last good value", key, exc_info=True)
                return cached[1]
            self._values[key] = (time.monotonic() + self._ttl, value)
            return value
        finally:
            lock.release()

    def invalidate(self, key: str) -> None:
        """Fetch on the next get(), keeping the current value as the fallback."""
        cached = self._values.get(key)
        if cached:
            self._values[key] = (0.0, cached[1])

    def _lock_for(self, key: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(key, threading.Lock())
```

```python
# app/clients/aws_values.py
import boto3
from botocore.config import Config

from app.clients.ttl_cache import TtlCache

# Fetched on the request path (per DB connection): fail fast and let TtlCache serve the
# last good value, instead of botocore's 60 s timeouts and legacy retries
CLIENT_CONFIG = Config(connect_timeout=1, read_timeout=2, retries={"mode": "standard", "max_attempts": 2})


def secrets_manager_cache(region: str, ttl_seconds: float) -> TtlCache:
    client = boto3.client("secretsmanager", region_name=region, config=CLIENT_CONFIG)
    return TtlCache(lambda secret_id: client.get_secret_value(SecretId=secret_id)["SecretString"], ttl_seconds)


def parameter_store_cache(region: str, ttl_seconds: float) -> TtlCache:
    client = boto3.client("ssm", region_name=region, config=CLIENT_CONFIG)
    return TtlCache(
        lambda name: client.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"], ttl_seconds
    )
```

- **One fetch per expiry.** The per-key lock lets one thread fetch; the others get the old value straight away, and wait only when there is no value yet.
- **Last good value on errors.** A Secrets Manager outage doesn't take the app down; the warning shows it in the logs. After a failed fetch the next try waits `retry_seconds` (30 s, at most the TTL), so an outage costs one slow call per backoff, not one per request.
- **`invalidate()`** forces the next read to fetch, e.g. after a value is known to be wrong ([[2b-settings-db-rotated-password]]). It keeps the old value as the fallback.

### On Lambda
- The cache lives per execution environment ([[1e-settings-lambda]]). Each environment fetches on its first use and refreshes on its own, so 100 warm environments make up to 100 calls per TTL.
- Each environment handles one request at a time, so the lock rarely has anyone to hold back; it matters on threaded servers. The backoff and the last good value matter on Lambda too.
- A fetch during a request adds its latency to that request, which is why the clients above use short boto3 timeouts.
- SnapStart doesn't apply: it doesn't support container images.

### Alternatives
- The AWS Parameters and Secrets Lambda Extension caches Secrets Manager and Parameter Store values in a local HTTP server (`localhost:2773`, 300 s TTL by default). It ships as a layer; a container image has to copy its files into `/opt`, like the AppConfig agent ([[2f-settings-feature-flags-appconfig]]).
- The Powertools for AWS Lambda parameters utility caches values in process, with a `max_age` per call.
- `aws-secretsmanager-caching`, an off-the-shelf cache for Secrets Manager with a one-hour default refresh.

## Pitfalls
- **No stampede protection.** Without the per-key lock, every request that sees an expired value calls AWS at once.
- **No backoff after a failed fetch.** Every request then retries AWS and waits for the timeout before getting the old value.
- **Failing requests on refresh errors.** Serve the last good value and log; fail only when there has never been a value.
- **Stale values forever.** "Last good value" hides a permanent outage. Alert on the refresh warnings.
- **Short TTLs.** Each fetch is an AWS API call with cost and throttling limits. Minutes, not seconds, for secrets.

## Related
- [[4a-settings-refreshing-values]]
- [[1e-settings-lambda]]
- [[2b-settings-db-rotated-password]]
- [[3b-settings-aws-sources]]
