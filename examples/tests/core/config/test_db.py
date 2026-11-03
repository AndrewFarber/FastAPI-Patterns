import pytest
from pydantic import ValidationError

from app.core.config.db import DbSettings

LOCAL = dict(host="localhost", user="app", name="shop", sslmode="disable")


def test_auth_method_selects_model():
    with pytest.raises(ValidationError, match="password"):
        DbSettings(
            **LOCAL,
            auth={"method": "iam", "region": "us-east-1", "password": "x"},
        )
    with pytest.raises(ValidationError):
        DbSettings(**LOCAL, auth={"password": "x"})


def test_verify_full_needs_a_ca():
    with pytest.raises(ValidationError, match="sslrootcert"):
        DbSettings(
            host="h",
            user="u",
            name="n",
            auth={"method": "password", "password": "p"},
        )
    with pytest.raises(ValidationError):
        DbSettings(
            host="h",
            user="u",
            name="n",
            sslrootcert="/no/such.pem",
            auth={"method": "password", "password": "p"},
        )
    with pytest.raises(ValidationError):
        DbSettings(
            host="h",
            user="u",
            name="n",
            sslrootcert="system",
            auth={"method": "password", "password": "p"},
        )
