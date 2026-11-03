import time
from datetime import timedelta

import pytest

from app.core.cache.ttl_cache import TtlCache


def test_ttl_cache_caches_and_expires():
    calls = []
    cache = TtlCache(
        lambda key: calls.append(key) or f"v{len(calls)}",
        ttl=timedelta(seconds=0.05),
    )
    assert cache.get("a") == "v1" and cache.get("a") == "v1"
    time.sleep(0.06)
    assert cache.get("a") == "v2"


def test_ttl_cache_serves_last_good_value():
    state = {"fail": False}

    def fetch(key):
        if state["fail"]:
            raise RuntimeError("AWS is down")
        return "good"

    cache = TtlCache(fetch, ttl=timedelta(seconds=0.01))
    assert cache.get("a") == "good"
    state["fail"] = True
    time.sleep(0.02)
    assert cache.get("a") == "good"
    with pytest.raises(RuntimeError):
        cache.get("never-fetched")


def test_ttl_cache_backs_off_after_a_failed_refresh():
    calls = []

    def fetch(key):
        calls.append(key)
        if len(calls) > 1:
            raise RuntimeError("AWS is down")
        return "good"

    cache = TtlCache(
        fetch, ttl=timedelta(seconds=0.01), retry=timedelta(seconds=60)
    )
    assert cache.get("a") == "good"
    time.sleep(0.02)
    assert [cache.get("a") for _ in range(10)] == ["good"] * 10
    assert len(calls) == 2


def test_ttl_cache_invalidate_keeps_the_fallback():
    state = {"fail": False}

    def fetch(key):
        if state["fail"]:
            raise RuntimeError("AWS is down")
        return "good"

    cache = TtlCache(fetch, ttl=timedelta(seconds=60))
    assert cache.get("a") == "good"
    state["fail"] = True
    cache.invalidate("a")
    assert cache.get("a") == "good"
