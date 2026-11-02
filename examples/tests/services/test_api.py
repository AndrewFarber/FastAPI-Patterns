def test_order_flow_across_services(client):
    ann = client.post("/users", json={"name": "ann"}).json()
    order = client.post("/orders", json={"user_id": ann["id"], "item": "book"})
    assert order.status_code == 201 and order.json()["status"] == "open"

    assert client.post(f"/users/{ann['id']}/deactivate").status_code == 204
    assert client.get("/orders", params={"user_id": ann["id"]}).json() == []

    refused = client.post("/orders", json={"user_id": ann["id"], "item": "pen"})
    assert refused.status_code == 409 and refused.json()["error"] == "UserNotActive"


def test_domain_errors_map_to_http(client):
    assert client.post("/users/999/deactivate").status_code == 404
