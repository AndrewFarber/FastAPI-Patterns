import pytest
from sqlalchemy.orm import Session

from app.services.orders.domain.entities import Order
from app.services.orders.domain.errors import OrderChangedError
from app.services.orders.infrastructure.repositories import SqlOrderRepository


def test_save_of_a_stale_copy_is_a_conflict(engine):
    with Session(engine) as session, session.begin():
        order_id = (
            SqlOrderRepository(session).add(Order(user_id=1, item="book")).id
        )
    with Session(engine) as first, Session(engine) as second:
        [mine], [theirs] = (
            SqlOrderRepository(first).list_for_user(1),
            SqlOrderRepository(second).list_for_user(1),
        )
        theirs.cancel()
        SqlOrderRepository(second).save(theirs)
        second.commit()
        mine.item = "pen"
        with pytest.raises(OrderChangedError, match=f"order {order_id}"):
            SqlOrderRepository(first).save(mine)
