import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config.settings import get_settings
from conftest import deliver, subscribe_queue


def test_app_serves_healthz_with_engine_and_cors(create_app, aws, monkeypatch):
    monkeypatch.setenv("CORS__ALLOW_ORIGINS", '["https://app.example.com"]')
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        assert app.state.engine.url.database == "shop_test"
        response = client.get(
            "/healthz", headers={"Origin": "https://app.example.com"}
        )
    assert response.json() == {"status": "ok", "app": "shop-api"}
    assert (
        response.headers["access-control-allow-origin"]
        == "https://app.example.com"
    )


def test_bad_config_fails_create_app(create_app, monkeypatch):
    monkeypatch.delenv("DB__HOST")
    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="host"):
        create_app()


def test_order_flow_across_services(client, workers, aws):
    orders_queue = subscribe_queue(aws, workers.orders)
    ann = client.post("/users", json={"name": "ann"}).json()
    order = client.post("/orders", json={"user_id": ann["id"], "item": "book"})
    assert order.status_code == 201 and order.json()["status"] == "open"
    open_orders = {"user_id": ann["id"], "status": "open"}

    assert client.post(f"/users/{ann['id']}/deactivate").status_code == 204
    [still_open] = client.get("/orders", params=open_orders).json()
    assert still_open["status"] == "open"

    assert deliver(orders_queue, workers.orders) == {"batchItemFailures": []}
    assert client.get("/orders", params=open_orders).json() == []
    [cancelled] = client.get("/orders", params={"user_id": ann["id"]}).json()
    assert cancelled["status"] == "cancelled"

    refused = client.post("/orders", json={"user_id": ann["id"], "item": "pen"})
    assert (
        refused.status_code == 409
        and refused.json()["error"] == "UserNotActiveError"
    )
