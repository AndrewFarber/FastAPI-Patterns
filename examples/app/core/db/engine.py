from sqlalchemy import Engine, create_engine

from app.core.config.db import DbSettings
from app.core.config.db_iam import IamAuth
from app.core.db.iam_auth import add_iam_token


def build_engine(db: DbSettings, application_name: str) -> Engine:
    engine = create_engine(
        str(db.url),
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_timeout=db.pool_timeout_seconds,
        pool_recycle=db.pool_recycle_seconds,
        pool_pre_ping=True,
        echo=db.echo,
        connect_args=db.connect_args(application_name),
    )
    if isinstance(db.auth, IamAuth):
        add_iam_token(engine, db)
    return engine
