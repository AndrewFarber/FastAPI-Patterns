class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class RuleViolationError(DomainError):
    pass


class ConflictError(DomainError):
    pass
