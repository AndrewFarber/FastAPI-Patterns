from typing import Annotated

from fastapi import Depends, Request

from app.core.dependencies.db import UnitOfWorkDep
from app.core.dependencies.settings import SettingsDep
from app.services import users
from app.services.orders.domain.protocols import OrderRepository, OrderSwitches, UserDirectory
from app.services.orders.infrastructure.repositories import SqlOrderRepository
from app.services.orders.infrastructure.switches import ParameterOrderSwitches


def get_order_repository(uow: UnitOfWorkDep) -> OrderRepository:
    return SqlOrderRepository(uow.session)


def get_user_directory(uow: UnitOfWorkDep) -> UserDirectory:
    return users.UsersApi(uow.session)


def get_order_switches(request: Request, settings: SettingsDep) -> OrderSwitches:
    return ParameterOrderSwitches(request.app.state.parameters, settings.switches.orders_paused)


OrderRepositoryDep = Annotated[OrderRepository, Depends(get_order_repository)]
UserDirectoryDep = Annotated[UserDirectory, Depends(get_user_directory)]
OrderSwitchesDep = Annotated[OrderSwitches, Depends(get_order_switches)]
