from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.services.users.domain.entities import User, UserStatus
from app.services.users.domain.errors import UserChangedError
from app.services.users.infrastructure.models import DbUser


def to_entity(row: DbUser) -> User:
    return User(
        id=row.id,
        name=row.name,
        status=UserStatus(row.status),
        version=row.version,
    )


class SqlUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> User | None:
        row = self._session.get(DbUser, user_id)
        return None if row is None else to_entity(row)

    def get_for_share(self, user_id: int) -> User | None:
        # FOR SHARE: the user can't change until this transaction ends
        query = (
            select(DbUser)
            .where(DbUser.id == user_id)
            .with_for_update(read=True)
        )
        row = self._session.scalars(
            query.execution_options(populate_existing=True)
        ).one_or_none()
        return None if row is None else to_entity(row)

    def add(self, user: User) -> User:
        row = DbUser(name=user.name, status=user.status)
        self._session.add(row)
        self._session.flush()
        user.id, user.version = row.id, row.version
        return user

    def save(self, user: User) -> None:
        result = self._session.execute(
            update(DbUser)
            .where(DbUser.id == user.id, DbUser.version == user.version)
            .values(
                name=user.name, status=user.status, version=user.version + 1
            )
        )
        if result.rowcount != 1:
            raise UserChangedError(user.id)
        user.version += 1
