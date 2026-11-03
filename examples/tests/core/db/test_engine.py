from app.core.config.db import DbSettings, PasswordAuth
from app.core.db.engine import create_engine, get_connect_args

LOCAL = dict(host="localhost", user="app", name="shop", sslmode="disable")


def test_password_auth_url_is_escaped_and_masked():
    db = DbSettings(
        **LOCAL, auth={"method": "password", "password": "p@ss/word"}
    )
    assert isinstance(db.auth, PasswordAuth)
    assert create_engine(db, "shop-api").url.password == "p@ss/word"
    assert "p@ss" not in repr(db)


def test_connect_args_verify_tls_and_name_the_app(ca_bundle):
    db = DbSettings(
        host="h",
        user="u",
        name="n",
        sslrootcert=ca_bundle,
        auth={"method": "password", "password": "p"},
    )
    assert get_connect_args(db, "shop-api") == {
        "sslmode": "verify-full",
        "connect_timeout": 10,
        "application_name": "shop-api",
        "sslrootcert": str(ca_bundle),
    }
