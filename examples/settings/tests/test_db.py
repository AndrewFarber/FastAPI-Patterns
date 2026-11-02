import json

import boto3
import psycopg
import pytest
from moto import mock_aws
from pydantic import ValidationError

from app.config.db import DbSettings, PasswordAuth
from app.db.engine import build_engine

LOCAL = dict(host="localhost", user="app", name="orders", sslmode="disable")


def test_password_auth_url_is_escaped_and_masked():
    db = DbSettings(**LOCAL, auth={"method": "password", "password": "p@ss/word"})
    assert isinstance(db.auth, PasswordAuth)
    assert build_engine(db, "orders-api").url.password == "p@ss/word"
    assert "p@ss" not in repr(db)


def test_auth_method_selects_model():
    with pytest.raises(ValidationError, match="password"):
        DbSettings(**LOCAL, auth={"method": "iam", "region": "us-east-1", "password": "x"})
    with pytest.raises(ValidationError):
        DbSettings(**LOCAL, auth={"password": "x"})


@pytest.fixture
def ca_bundle(tmp_path):
    path = tmp_path / "ca.pem"
    path.write_text("")
    return path


def test_verify_full_needs_a_ca():
    with pytest.raises(ValidationError, match="sslrootcert"):
        DbSettings(host="h", user="u", name="n", auth={"method": "password", "password": "p"})
    with pytest.raises(ValidationError):
        DbSettings(host="h", user="u", name="n", sslrootcert="/no/such.pem", auth={"method": "password", "password": "p"})
    with pytest.raises(ValidationError):                # psycopg[binary] can't find the OS trust store
        DbSettings(host="h", user="u", name="n", sslrootcert="system", auth={"method": "password", "password": "p"})


def test_connect_args(ca_bundle):
    db = DbSettings(host="h", user="u", name="n", sslrootcert=ca_bundle, auth={"method": "password", "password": "p"})
    assert db.connect_args("orders-api") == {
        "sslmode": "verify-full", "connect_timeout": 10, "application_name": "orders-api", "sslrootcert": str(ca_bundle),
    }


def test_iam_token_per_connection(ca_bundle):
    db = DbSettings(host="orders.abc123.us-east-1.rds.amazonaws.com", user="orders_app", name="orders",
                    sslrootcert=ca_bundle, auth={"method": "iam", "region": "us-east-1"})
    engine = build_engine(db, "orders-api")
    cparams = {}
    for listener in engine.dialect.dispatch.do_connect:
        listener(engine.dialect, None, [], cparams)
    assert "Action=connect" in cparams["password"]


def test_iam_requires_tls():
    with pytest.raises(ValueError, match="requires TLS"):
        build_engine(DbSettings(**LOCAL, auth={"method": "iam", "region": "us-east-1"}), "orders-api")


def test_rotated_password_retries_after_rotation(monkeypatch):
    with mock_aws():
        sm = boto3.client("secretsmanager")
        sm.create_secret(Name="orders/prd/db-app", SecretString=json.dumps({"username": "orders_app", "password": "old"}))
        db = DbSettings(**LOCAL, auth={"method": "rotated_secret", "secret_id": "orders/prd/db-app", "region": "us-east-1"})
        engine = build_engine(db, "orders-api")
        [listener] = list(engine.dialect.dispatch.do_connect)

        attempts = []

        def fake_connect(*cargs, **cparams):
            attempts.append((cparams["user"], cparams["password"]))
            if cparams["password"] != "new":
                raise psycopg.OperationalError("password authentication failed")
            return "connection"

        monkeypatch.setattr(engine.dialect, "connect", fake_connect)
        with pytest.raises(psycopg.OperationalError):
            listener(engine.dialect, None, [], {})          # the secret hasn't changed: no retry
        assert attempts == [("orders_app", "old")]
        sm.put_secret_value(SecretId="orders/prd/db-app",
                            SecretString=json.dumps({"username": "orders_app_clone", "password": "new"}))
        attempts.clear()
        assert listener(engine.dialect, None, [], {}) == "connection"
        assert attempts == [("orders_app", "old"), ("orders_app_clone", "new")]   # cached "old", then the new secret

