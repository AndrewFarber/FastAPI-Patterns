---
title: "Refreshing settings values"
category: project-structure
related:
  - "[[settings-guide]]"
---

# Refreshing settings values

## Overview
`Settings` stays frozen and is built once. A redeploy is the default way to change a value; a value that can't wait for one is read through a `TtlCache` (`core/cache/`) around an AWS client (`core/aws/`), and settings hold only *where* and *how often* to fetch it. An expired key is fetched on the next read, and the last good value is served with a backoff when the source is down.

## Rules
- **Never mutate or rebuild settings.** Startup objects (engine, middleware, mounted routers) would keep the old values, and a failed rebuild would fail every request; the cache is a client built at startup.
- **No locks.** Sync routes share the cache across threadpool threads; each dict read and write is atomic, so threads never see a torn entry. At expiry, threads that read the key at the same moment each fetch it: a few extra calls once per TTL, each capped by the client timeouts.
- **Last good value on errors,** with one warning and a `retry` backoff; raise only when there has never been a value.
- **`invalidate()` keeps the fallback** and forces the next read to fetch, for a caller that knows the value is stale.
- **Read each value once at startup.** The first `get()` raises when there is no value yet; reading it in the lifespan turns a missing parameter or permission into a failed deploy, and from then on there is always a last good value to serve.
- **Keep live values outside `AWS_SSM_PATH`.** The settings source ([[settings-aws-sources]]) loads every parameter under that path into `Settings`, where `extra="forbid"` rejects one it doesn't know: `/shop/switches/orders-paused`, not `/shop/prd/switches/...`.
- **Short boto3 timeouts on the request path** (1 s connect, 2 s read, 2 attempts).
- **TTLs in minutes for secrets.** Each fetch is a billed, throttled API call, once per process.
- **Caches live per process;** each new instance reads fresh values anyway.
- **Runtime changes reach every running version at once,** unlike a deploy, which can be rolled out gradually and rolled back.

## Code example
```python
# app/core/cache/ttl_cache.py
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
```

```python
# app/core/aws/values.py
from datetime import timedelta

import boto3
from botocore.config import Config

from app.core.cache.ttl_cache import TtlCache

CLIENT_CONFIG = Config(
    connect_timeout=1,
    read_timeout=2,
    retries={"mode": "standard", "max_attempts": 2},
)


def create_secrets_manager_cache(region: str, ttl: timedelta) -> TtlCache:
    client = boto3.client(
        "secretsmanager", region_name=region, config=CLIENT_CONFIG
    )
    return TtlCache(
        lambda secret_id: client.get_secret_value(SecretId=secret_id)[
            "SecretString"
        ],
        ttl,
    )


def create_parameter_store_cache(region: str, ttl: timedelta) -> TtlCache:
    client = boto3.client("ssm", region_name=region, config=CLIENT_CONFIG)
    return TtlCache(
        lambda name: client.get_parameter(Name=name, WithDecryption=True)[
            "Parameter"
        ]["Value"],
        ttl,
    )
```

An entry point builds the cache once at startup, from a sub-model that names the secret or parameter and its TTL, and passes it to whatever reads the value. The example app pauses ordering this way, without a redeploy. Settings hold only where the switch lives and how often to read it:

```python
# app/core/config/switches.py
from pydantic import BaseModel, ConfigDict, Field


class SwitchesSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str
    ttl_seconds: float = Field(default=30, gt=0)
    orders_paused: str = Field(pattern=r"^/")
```

The lifespan builds the cache and reads the switch once, so a missing parameter fails startup instead of every order:

```python
# app/main.py (fragment)
    app.state.parameters = create_parameter_store_cache(
        settings.switches.region,
        timedelta(seconds=settings.switches.ttl_seconds),
    )
    # A missing parameter fails startup, not every order
    app.state.parameters.get(settings.switches.orders_paused)
```

Orders states what it needs as a `Protocol`, `OrderSwitches` ([[services-calls]]); its infrastructure answers from the cache, and `api/dependencies.py` builds one per request from `app.state.parameters` and `settings.switches.orders_paused`:

```python
# app/services/orders/infrastructure/switches.py
from app.core.cache.ttl_cache import TtlCache


class SsmOrderSwitches:
    def __init__(self, parameters: TtlCache, paused_parameter: str) -> None:
        self._parameters = parameters
        self._paused_parameter = paused_parameter

    def is_ordering_paused(self) -> bool:
        return self._parameters.get(self._paused_parameter) == "true"
```

`place_order` raises `OrderingPausedError` (409) while the parameter is `true`. Its tests pass a fake `OrderSwitches`; the API test sets the parameter in `moto` and calls `invalidate()` so the next read sees it.
