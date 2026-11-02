from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from app.core.db.unit_of_work import UnitOfWork


def get_unit_of_work(request: Request) -> Iterator[UnitOfWork]:
    with UnitOfWork(request.app.state.engine, request.app.state.relay) as uow:
        yield uow


UnitOfWorkDep = Annotated[
    UnitOfWork, Depends(get_unit_of_work, scope="function")
]
