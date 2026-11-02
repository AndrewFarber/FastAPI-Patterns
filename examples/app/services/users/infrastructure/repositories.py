from sqlalchemy.orm import Session

from app.services.users.domain.entities import User, UserStatus
from app.services.users.infrastructure.models import UserRow


def to_entity(row: UserRow) -> User:
    return User(id=row.id, name=row.name, status=UserStatus(row.status))


class SqlUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> User | None:
        row = self._session.get(UserRow, user_id)
        return None if row is None else to_entity(row)

    def add(self, user: User) -> User:
        row = UserRow(name=user.name, status=user.status)
        self._session.add(row)
        self._session.flush()
        user.id = row.id
        return user

    def save(self, user: User) -> None:
        row = self._session.get_one(UserRow, user.id)
        row.name, row.status = user.name, user.status
