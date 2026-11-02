import boto3

from conftest import TEST_VALUES, deliver, subscribe_queue


def test_order_flow_across_services(client, workers, aws):
    orders_queue = subscribe_queue(aws, workers.orders)
    ann = client.post("/users", json={"name": "ann"}).json()
    order = client.post("/orders", json={"user_id": ann["id"], "item": "book"})
    assert order.status_code == 201 and order.json()["status"] == "open"

    assert client.post(f"/users/{ann['id']}/deactivate").status_code == 204
    assert client.get("/orders", params={"user_id": ann["id"]}).json()[0]["status"] == "open"

    assert deliver(orders_queue, workers.orders) == {"batchItemFailures": []}
    assert client.get("/orders", params={"user_id": ann["id"]}).json() == []

    refused = client.post("/orders", json={"user_id": ann["id"], "item": "pen"})
    assert refused.status_code == 409 and refused.json()["error"] == "UserNotActive"


def test_domain_errors_map_to_http(client):
    assert client.post("/users/999/deactivate").status_code == 404


def test_paused_ordering_is_refused(client):
    boto3.client("ssm").put_parameter(Name=TEST_VALUES["switches"]["orders_paused"], Value="true", Overwrite=True)
    client.app.state.parameters.invalidate(TEST_VALUES["switches"]["orders_paused"])
    ann = client.post("/users", json={"name": "ann"}).json()
    refused = client.post("/orders", json={"user_id": ann["id"], "item": "book"})
    assert refused.status_code == 409 and refused.json()["error"] == "OrderingPaused"
