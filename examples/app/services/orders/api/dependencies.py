from typing import Annotated

from fastapi import Depends

from app.core.dependencies.db import UnitOfWorkDep
from app.services import users
from app.services.orders.domain.protocols import OrderRepository, UserDirectory
from app.services.orders.infrastructure.repositories import SqlOrderRepository


def get_order_repository(uow: UnitOfWorkDep) -> OrderRepository:
    return SqlOrderRepository(uow.session)


def get_user_directory(uow: UnitOfWorkDep) -> UserDirectory:
    return users.UsersApi(uow.session)


OrderRepositoryDep = Annotated[OrderRepository, Depends(get_order_repository)]
UserDirectoryDep = Annotated[UserDirectory, Depends(get_user_directory)]
