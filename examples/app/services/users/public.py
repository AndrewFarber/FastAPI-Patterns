from sqlalchemy.orm import Session

from app.services.users.infrastructure.repositories import SqlUserRepository


class UsersApi:
    def __init__(self, session: Session) -> None:
        self._users = SqlUserRepository(session)

    def is_active(self, user_id: int) -> bool:
        user = self._users.get(user_id)
        return user is not None and user.is_active()
