import boto3
from sqlalchemy import Engine, event

from app.core.config.db import DbSettings
from app.core.config.db_iam import IamAuth


def add_iam_token(engine: Engine, db: DbSettings) -> None:
    assert isinstance(db.auth, IamAuth)
    if db.sslmode == "disable":
        raise ValueError("IAM database authentication requires TLS")
    rds = boto3.client("rds", region_name=db.auth.region)

    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        cparams["password"] = rds.generate_db_auth_token(
            DBHostname=db.host, Port=db.port, DBUsername=db.user, Region=db.auth.region
        )
