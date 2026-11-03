import pytest

from app.core.config.db import DbSettings
from app.core.db.engine import create_engine

LOCAL = dict(host="localhost", user="app", name="shop", sslmode="disable")


def test_iam_sets_a_token_per_connection(ca_bundle):
    db = DbSettings(
        host="shop.abc123.us-east-1.rds.amazonaws.com",
        user="shop_app",
        name="shop",
        sslrootcert=ca_bundle,
        auth={"method": "iam", "region": "us-east-1"},
    )
    engine = create_engine(db, "shop-api")
    cparams = {}
    for listener in engine.dialect.dispatch.do_connect:
        listener(engine.dialect, None, [], cparams)
    assert "Action=connect" in cparams["password"]


def test_iam_requires_tls():
    with pytest.raises(ValueError, match="requires TLS"):
        create_engine(
            DbSettings(**LOCAL, auth={"method": "iam", "region": "us-east-1"}),
            "shop-api",
        )
