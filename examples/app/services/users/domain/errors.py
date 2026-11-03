from app.shared.errors.base import (
    ConflictError,
    NotFoundError,
    RuleViolationError,
)


class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: int | None) -> None:
        super().__init__(f"user {user_id} not found")


class UserAlreadyDeactivatedError(RuleViolationError):
    def __init__(self, user_id: int | None) -> None:
        super().__init__(f"user {user_id} is already deactivated")


class UserChangedError(ConflictError):
    def __init__(self, user_id: int | None) -> None:
        super().__init__(
            f"user {user_id} was changed by another request; reload and retry"
        )
