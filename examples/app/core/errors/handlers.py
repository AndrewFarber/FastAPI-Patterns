from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.shared.errors.base import (
    ConflictError,
    DomainError,
    NotFoundError,
    RuleViolationError,
)

STATUS_CODES: dict[type[DomainError], int] = {
    NotFoundError: 404,
    RuleViolationError: 409,
    ConflictError: 409,
}


def domain_error_response(request: Request, error: Exception) -> JSONResponse:
    status = next(
        (
            code
            for kind, code in STATUS_CODES.items()
            if isinstance(error, kind)
        ),
        400,
    )
    return JSONResponse(
        {"detail": str(error), "error": type(error).__name__},
        status_code=status,
    )


def register(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_response)
