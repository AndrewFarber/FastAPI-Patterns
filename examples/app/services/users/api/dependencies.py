from typing import Annotated

from fastapi import Depends

from app.core.dependencies.db import UnitOfWorkDep
from app.services.users.domain.protocols import UserRepository
from app.services.users.infrastructure.repositories import SqlUserRepository


def get_user_repository(uow: UnitOfWorkDep) -> UserRepository:
    return SqlUserRepository(uow.session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]
