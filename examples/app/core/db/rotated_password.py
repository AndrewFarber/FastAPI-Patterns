import json

import psycopg
from sqlalchemy import Engine, event

from app.core.aws.values import secrets_manager_cache
from app.core.config.db import DbSettings
from app.core.config.db_rotated import RotatedSecretAuth


def add_rotated_password(engine: Engine, db: DbSettings) -> None:
    assert isinstance(db.auth, RotatedSecretAuth)
    auth = db.auth
    secrets = secrets_manager_cache(auth.region, auth.ttl_seconds)

    @event.listens_for(engine, "do_connect")
    def connect_with_current_password(dialect, conn_rec, cargs, cparams):
        secret = json.loads(secrets.get(auth.secret_id))
        cparams["user"] = secret["username"]
        cparams["password"] = secret["password"]
        try:
            return dialect.connect(*cargs, **cparams)
        except psycopg.OperationalError:
            secrets.invalidate(auth.secret_id)
            fresh = json.loads(secrets.get(auth.secret_id))
            if fresh == secret:
                raise
        cparams["user"] = fresh["username"]
        cparams["password"] = fresh["password"]
        return dialect.connect(*cargs, **cparams)
