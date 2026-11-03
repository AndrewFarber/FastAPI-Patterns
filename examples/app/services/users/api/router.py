from fastapi import APIRouter

from app.core.dependencies.db import UnitOfWorkDep
from app.services.users.api.dependencies import UserRepositoryDep
from app.services.users.api.schemas import UserCreate, UserOut
from app.services.users.use_cases.deactivate_user import (
    DeactivateUserCommand,
    deactivate_user,
)
from app.services.users.use_cases.register_user import (
    RegisterUserCommand,
    register_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=201)
def post_user(body: UserCreate, user_repository: UserRepositoryDep) -> UserOut:
    user = register_user(RegisterUserCommand(name=body.name), user_repository)
    return UserOut(id=user.id, name=user.name, status=user.status)


@router.post("/{user_id}/deactivate", status_code=204)
def post_user_deactivate(
    user_id: int,
    user_repository: UserRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> None:
    deactivate_user(
        DeactivateUserCommand(user_id=user_id),
        user_repository,
        unit_of_work.event_publisher,
    )
