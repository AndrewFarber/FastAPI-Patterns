class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class RuleViolation(DomainError):
    pass


class ConflictError(DomainError):
    pass
