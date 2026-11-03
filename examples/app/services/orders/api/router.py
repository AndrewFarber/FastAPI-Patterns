from fastapi import APIRouter

from app.services.orders.api.dependencies import (
    OrderRepositoryDep,
    OrderSwitchesDep,
    UserDirectoryDep,
)
from app.services.orders.api.schemas import OrderCreate, OrderRead
from app.services.orders.domain.entities import OrderStatus
from app.services.orders.use_cases.place_order import (
    PlaceOrderCommand,
    place_order,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", status_code=201)
def post_order(
    body: OrderCreate,
    order_repository: OrderRepositoryDep,
    user_directory: UserDirectoryDep,
    order_switches: OrderSwitchesDep,
) -> OrderRead:
    order = place_order(
        PlaceOrderCommand(user_id=body.user_id, item=body.item),
        order_repository,
        user_directory,
        order_switches,
    )
    return OrderRead(
        id=order.id, user_id=order.user_id, item=order.item, status=order.status
    )


@router.get("")
def get_orders(
    user_id: int,
    order_repository: OrderRepositoryDep,
    status: OrderStatus | None = None,
) -> list[OrderRead]:
    return [
        OrderRead(
            id=order.id,
            user_id=order.user_id,
            item=order.item,
            status=order.status,
        )
        for order in order_repository.list_for_user(user_id, status)
    ]
