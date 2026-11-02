import boto3
from sqlalchemy import Engine, event

from app.config.db import DbSettings
from app.config.db_iam import IamAuth


def add_iam_token(engine: Engine, db: DbSettings) -> None:
    """Use a fresh IAM auth token as the password for each new connection."""
    assert isinstance(db.auth, IamAuth)
    if db.sslmode == "disable":
        raise ValueError("IAM database authentication requires TLS")
    rds = boto3.client("rds", region_name=db.auth.region)

    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        # Signed locally with the app's AWS credentials: no network call.
        # boto3 refreshes role credentials itself, so the client can be reused.
        cparams["password"] = rds.generate_db_auth_token(
            DBHostname=db.host, Port=db.port, DBUsername=db.user, Region=db.auth.region
        )
