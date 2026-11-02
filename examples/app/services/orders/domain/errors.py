from app.shared.exceptions.base import RuleViolation


class UserNotActive(RuleViolation):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"user {user_id} is not active")
