import time

import pytest
from cachetools.func import ttl_cache

from app.core.config.settings import Settings


def test_rebuild_on_ttl(test_env, monkeypatch):
    @ttl_cache(maxsize=1, ttl=0.05)
    def get_settings() -> Settings:
        return Settings()

    first = get_settings()
    assert get_settings() is first
    monkeypatch.setenv("DB__HOST", "new-host")
    assert get_settings() is first
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
    assert len(calls) == 3
