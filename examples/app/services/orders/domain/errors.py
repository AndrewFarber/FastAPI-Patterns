from app.shared.exceptions.base import ConflictError, RuleViolation


class UserNotActive(RuleViolation):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"user {user_id} is not active")


class OrderingPaused(RuleViolation):
    def __init__(self) -> None:
        super().__init__("ordering is paused; try again later")


class OrderChanged(ConflictError):
    def __init__(self, order_id: int | None) -> None:
        super().__init__(f"order {order_id} was changed by another request; reload and retry")
