from fastapi import APIRouter

from app.core.dependencies.db import UnitOfWorkDep
from app.services.users.api.dependencies import UserRepositoryDep
from app.services.users.api.schemas import UserIn, UserOut
from app.services.users.use_cases.deactivate_user import DeactivateUser, deactivate_user
from app.services.users.use_cases.register_user import RegisterUser, register_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=201)
def post_user(body: UserIn, users: UserRepositoryDep) -> UserOut:
    user = register_user(RegisterUser(name=body.name), users)
    return UserOut(id=user.id, name=user.name, status=user.status)


@router.post("/{user_id}/deactivate", status_code=204)
def post_deactivate(user_id: int, users: UserRepositoryDep, uow: UnitOfWorkDep) -> None:
    deactivate_user(DeactivateUser(user_id=user_id), users, uow.events)
