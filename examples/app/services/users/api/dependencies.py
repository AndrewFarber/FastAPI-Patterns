from typing import Annotated

from fastapi import Depends

from app.core.dependencies.db import UnitOfWorkDep
from app.services.users.domain.protocols import UserRepository
from app.services.users.infrastructure.repositories import SqlUserRepository


def get_user_repository(unit_of_work: UnitOfWorkDep) -> UserRepository:
    return SqlUserRepository(unit_of_work.session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]
