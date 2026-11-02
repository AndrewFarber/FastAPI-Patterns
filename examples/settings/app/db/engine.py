from sqlalchemy import Engine, create_engine

from app.config.db import DbSettings
from app.config.db_iam import IamAuth
from app.config.db_rotated import RotatedSecretAuth
from app.db.iam_auth import add_iam_token
from app.db.rotated_password import add_rotated_password


def build_engine(db: DbSettings, application_name: str) -> Engine:
    engine = create_engine(
        str(db.url),
        pool_size=db.pool_size,
        max_overflow=db.max_overflow,
        pool_timeout=db.pool_timeout_seconds,
        pool_recycle=db.pool_recycle_seconds,
        pool_pre_ping=True,               # drop dead connections before use
        echo=db.echo,
        connect_args=db.connect_args(application_name),
    )
    # Auth methods without a static password supply it per connection
    if isinstance(db.auth, IamAuth):
        add_iam_token(engine, db)
    elif isinstance(db.auth, RotatedSecretAuth):
        add_rotated_password(engine, db)
    return engine
