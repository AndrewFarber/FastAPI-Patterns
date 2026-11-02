from sqlalchemy import URL, Engine, create_engine

from app.core.config.db import DbSettings, PasswordAuth
from app.core.config.db_iam import IamAuth
from app.core.db.iam_auth import add_iam_token


def build_engine(db: DbSettings, application_name: str) -> Engine:
    engine = create_engine(
        _url(db),
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_timeout=db.pool_timeout_seconds,
        pool_recycle=db.pool_recycle_seconds,
        pool_pre_ping=True,
        echo=db.echo,
        connect_args=connect_args(db, application_name),
    )
    if isinstance(db.auth, IamAuth):
        add_iam_token(engine, db)
    return engine


def connect_args(db: DbSettings, application_name: str) -> dict[str, str | int]:
    args: dict[str, str | int] = {
        "sslmode": db.sslmode,
        "connect_timeout": db.connect_timeout_seconds,
        "application_name": application_name,
    }
    if db.sslrootcert is not None:
        args["sslrootcert"] = str(db.sslrootcert)
    return args


def _url(db: DbSettings) -> URL:
    password = db.auth.password.get_secret_value() if isinstance(db.auth, PasswordAuth) else None
    return URL.create(db.scheme, username=db.user, password=password, host=db.host, port=db.port, database=db.name)
