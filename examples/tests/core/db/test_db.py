import pytest
from pydantic import ValidationError

from app.core.config.db import DbSettings, PasswordAuth
from app.core.db.engine import build_engine, connect_args

LOCAL = dict(host="localhost", user="app", name="shop", sslmode="disable")


def test_password_auth_url_is_escaped_and_masked():
    db = DbSettings(
        **LOCAL, auth={"method": "password", "password": "p@ss/word"}
    )
    assert isinstance(db.auth, PasswordAuth)
    assert build_engine(db, "shop-api").url.password == "p@ss/word"
    assert "p@ss" not in repr(db)


def test_auth_method_selects_model():
    with pytest.raises(ValidationError, match="password"):
        DbSettings(
            **LOCAL,
            auth={"method": "iam", "region": "us-east-1", "password": "x"},
        )
    with pytest.raises(ValidationError):
        DbSettings(**LOCAL, auth={"password": "x"})


@pytest.fixture
def ca_bundle(tmp_path):
    path = tmp_path / "ca.pem"
    path.write_text("")
    return path


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


def test_connect_args(ca_bundle):
    db = DbSettings(
        host="h",
        user="u",
        name="n",
        sslrootcert=ca_bundle,
        auth={"method": "password", "password": "p"},
    )
    assert connect_args(db, "shop-api") == {
        "sslmode": "verify-full",
        "connect_timeout": 10,
        "application_name": "shop-api",
        "sslrootcert": str(ca_bundle),
    }


def test_iam_token_per_connection(ca_bundle):
    db = DbSettings(
        host="shop.abc123.us-east-1.rds.amazonaws.com",
        user="shop_app",
        name="shop",
        sslrootcert=ca_bundle,
        auth={"method": "iam", "region": "us-east-1"},
    )
    engine = build_engine(db, "shop-api")
    cparams = {}
    for listener in engine.dialect.dispatch.do_connect:
        listener(engine.dialect, None, [], cparams)
    assert "Action=connect" in cparams["password"]


def test_iam_requires_tls():
    with pytest.raises(ValueError, match="requires TLS"):
        build_engine(
            DbSettings(**LOCAL, auth={"method": "iam", "region": "us-east-1"}),
            "shop-api",
        )
