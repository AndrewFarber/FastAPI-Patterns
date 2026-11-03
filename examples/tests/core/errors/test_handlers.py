def test_domain_errors_map_to_http(client):
    response = client.post("/users/999/deactivate")
    assert (
        response.status_code == 404
        and response.json()["error"] == "UserNotFoundError"
    )
