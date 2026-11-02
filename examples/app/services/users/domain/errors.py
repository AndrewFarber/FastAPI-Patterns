from app.shared.exceptions.base import ConflictError, NotFoundError, RuleViolation


class UserNotFound(NotFoundError):
    def __init__(self, user_id: int | None) -> None:
        super().__init__(f"user {user_id} not found")


class UserAlreadyDeactivated(RuleViolation):
    def __init__(self, user_id: int | None) -> None:
        super().__init__(f"user {user_id} is already deactivated")


class UserChanged(ConflictError):
    def __init__(self, user_id: int | None) -> None:
        super().__init__(f"user {user_id} was changed by another request; reload and retry")
