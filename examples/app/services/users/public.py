from sqlalchemy.orm import Session

from app.services.users.infrastructure.repositories import SqlUserRepository


class UsersApi:
    def __init__(self, session: Session) -> None:
        self._users = SqlUserRepository(session)

    def is_active(self, user_id: int) -> bool:
        # The share lock keeps the answer true until the caller commits:
        # a deactivation waits for the caller's transaction, so its
        # UserDeactivated handler sees what the caller wrote
        user = self._users.get_for_share(user_id)
        return user is not None and user.is_active()
