import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config.settings import get_settings


def test_app_serves_healthz_with_engine_and_cors(create_app, aws, monkeypatch):
    monkeypatch.setenv("CORS__ALLOW_ORIGINS", '["https://app.example.com"]')
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        assert app.state.engine.url.database == "shop_test"
        response = client.get("/healthz", headers={"Origin": "https://app.example.com"})
    assert response.json() == {"status": "ok", "app": "shop-api"}
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"


def test_bad_config_fails_create_app(create_app, monkeypatch):
    monkeypatch.delenv("DB__HOST")
    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="host"):
        create_app()
