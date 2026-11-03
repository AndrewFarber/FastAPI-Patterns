import json

from conftest import create_test_env


def test_create_test_env_encodes_json():
    env = create_test_env()
    assert env["DB__HOST"] == "localhost"
    assert json.loads(env["DB__AUTH"]) == {
        "method": "password",
        "password": "test",
    }
