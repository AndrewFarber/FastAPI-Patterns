import boto3

from conftest import TEST_VALUES


def test_paused_ordering_is_refused(client):
    boto3.client("ssm").put_parameter(
        Name=TEST_VALUES["switches"]["orders_paused"],
        Value="true",
        Overwrite=True,
    )
    client.app.state.parameters.invalidate(
        TEST_VALUES["switches"]["orders_paused"]
    )
    ann = client.post("/users", json={"name": "ann"}).json()
    refused = client.post(
        "/orders", json={"user_id": ann["id"], "item": "book"}
    )
    assert (
        refused.status_code == 409
        and refused.json()["error"] == "OrderingPausedError"
    )
