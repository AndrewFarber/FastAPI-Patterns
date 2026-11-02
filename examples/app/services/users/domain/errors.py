from app.shared.exceptions.base import NotFoundError, RuleViolation


class UserNotFound(NotFoundError):
    def __init__(self, user_id: int | None) -> None:
        super().__init__(f"user {user_id} not found")


class UserAlreadyDeactivated(RuleViolation):
    def __init__(self, user_id: int | None) -> None:
        super().__init__(f"user {user_id} is already deactivated")
