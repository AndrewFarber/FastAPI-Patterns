import json

import psycopg
from sqlalchemy import Engine, event

from app.clients.aws_values import secrets_manager_cache
from app.config.db import DbSettings
from app.config.db_rotated import RotatedSecretAuth


def add_rotated_password(engine: Engine, db: DbSettings) -> None:
    """Use the current Secrets Manager password for each new connection."""
    assert isinstance(db.auth, RotatedSecretAuth)
    auth = db.auth
    secrets = secrets_manager_cache(auth.region, auth.ttl_seconds)

    @event.listens_for(engine, "do_connect")
    def connect_with_current_password(dialect, conn_rec, cargs, cparams):
        secret = json.loads(secrets.get(auth.secret_id))       # {"username": ..., "password": ...}
        cparams["user"] = secret["username"]
        cparams["password"] = secret["password"]
        try:
            return dialect.connect(*cargs, **cparams)
        except psycopg.OperationalError:
            # The password may have just rotated. libpq gives connection errors no SQLSTATE,
            # so retry only if Secrets Manager now has a different secret: a DB outage fails once.
            secrets.invalidate(auth.secret_id)
            fresh = json.loads(secrets.get(auth.secret_id))
            if fresh == secret:
                raise
        cparams["user"] = fresh["username"]
        cparams["password"] = fresh["password"]
        return dialect.connect(*cargs, **cparams)
