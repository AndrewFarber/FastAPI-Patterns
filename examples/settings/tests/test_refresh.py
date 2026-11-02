import threading
import time

import boto3
import pytest
from cachetools.func import ttl_cache
from moto import mock_aws

from app.clients.aws_values import parameter_store_cache, secrets_manager_cache
from app.clients.ttl_cache import TtlCache
from app.config.settings import Settings


def test_ttl_cache_caches_and_expires():
    calls = []
    cache = TtlCache(lambda key: calls.append(key) or f"v{len(calls)}", ttl_seconds=0.05)
    assert cache.get("a") == "v1" and cache.get("a") == "v1"
    time.sleep(0.06)
    assert cache.get("a") == "v2"


def test_ttl_cache_serves_last_good_value():
    state = {"fail": False}

    def fetch(key):
        if state["fail"]:
            raise RuntimeError("AWS is down")
        return "good"

    cache = TtlCache(fetch, ttl_seconds=0.01)
    assert cache.get("a") == "good"
    state["fail"] = True
    time.sleep(0.02)
    assert cache.get("a") == "good"
    with pytest.raises(RuntimeError):
        cache.get("never-fetched")


def test_ttl_cache_fetches_once_under_concurrency():
    calls = []

    def slow(key):
        calls.append(key)
        time.sleep(0.1)
        return "v"

    cache = TtlCache(slow, ttl_seconds=60)
    threads = [threading.Thread(target=cache.get, args=("a",)) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1


def test_ttl_cache_backs_off_after_a_failed_refresh():
    calls = []

    def fetch(key):
        calls.append(key)
        if len(calls) > 1:
            raise RuntimeError("AWS is down")
        return "good"

    cache = TtlCache(fetch, ttl_seconds=0.01, retry_seconds=60)
    assert cache.get("a") == "good"
    time.sleep(0.02)
    assert [cache.get("a") for _ in range(10)] == ["good"] * 10
    assert len(calls) == 2                                    # one failed refresh, then the backoff


def test_ttl_cache_serves_old_value_while_refreshing():
    started, release = threading.Event(), threading.Event()
    values = iter(["old", "new"])

    def fetch(key):
        value = next(values)
        if value == "new":
            started.set()
            release.wait(1)
        return value

    cache = TtlCache(fetch, ttl_seconds=0.01)
    assert cache.get("a") == "old"
    time.sleep(0.02)
    refresher = threading.Thread(target=cache.get, args=("a",))
    refresher.start()
    started.wait(1)
    assert cache.get("a") == "old"                            # doesn't wait for the slow fetch
    release.set()
    refresher.join()
    assert cache.get("a") == "new"


def test_ttl_cache_invalidate_keeps_the_fallback():
    state = {"fail": False}

    def fetch(key):
        if state["fail"]:
            raise RuntimeError("AWS is down")
        return "good"

    cache = TtlCache(fetch, ttl_seconds=60)
    assert cache.get("a") == "good"
    state["fail"] = True
    cache.invalidate("a")
    assert cache.get("a") == "good"                           # refetch failed: last good value


def test_aws_value_caches():
    with mock_aws():
        boto3.client("secretsmanager").create_secret(Name="s", SecretString="secret-value")
        boto3.client("ssm").put_parameter(Name="/p", Value="parameter-value", Type="SecureString")
        assert secrets_manager_cache("us-east-1", 60).get("s") == "secret-value"
        assert parameter_store_cache("us-east-1", 60).get("/p") == "parameter-value"


def test_rebuild_on_ttl(test_env, monkeypatch):
    @ttl_cache(maxsize=1, ttl=0.05)
    def get_settings() -> Settings:
        return Settings()

    first = get_settings()
    assert get_settings() is first
    monkeypatch.setenv("DB__HOST", "new-host")
    assert get_settings() is first                            # cached until the TTL expires
    time.sleep(0.06)
    assert get_settings().db.host == "new-host"


def test_rebuild_failures_are_not_cached(test_env, monkeypatch):
    calls = []

    @ttl_cache(maxsize=1, ttl=300)
    def get_settings() -> Settings:
        calls.append(1)
        return Settings()

    monkeypatch.setenv("DB__PORT", "not-a-port")
    for _ in range(3):
        with pytest.raises(ValueError):
            get_settings()
    assert len(calls) == 3                                    # every call retries the full rebuild
