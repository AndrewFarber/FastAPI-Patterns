class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class RuleViolation(DomainError):
    pass
