from fastapi import APIRouter

from app.services.orders.api.dependencies import OrderRepositoryDep, UserDirectoryDep
from app.services.orders.api.schemas import OrderIn, OrderOut
from app.services.orders.use_cases.place_order import PlaceOrder, place_order

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", status_code=201)
def post_order(body: OrderIn, orders: OrderRepositoryDep, users: UserDirectoryDep) -> OrderOut:
    order = place_order(PlaceOrder(user_id=body.user_id, item=body.item), orders, users)
    return OrderOut(id=order.id, user_id=order.user_id, item=order.item, status=order.status)


@router.get("")
def get_open_orders(user_id: int, orders: OrderRepositoryDep) -> list[OrderOut]:
    return [OrderOut(id=o.id, user_id=o.user_id, item=o.item, status=o.status) for o in orders.open_for_user(user_id)]
