from sqlalchemy.orm import Session

from app.services import users
from app.services.users.domain.entities import User
from app.services.users.infrastructure.repositories import SqlUserRepository


def test_is_active_applies_the_users_rule(engine):
    with Session(engine) as session:
        user_repository = SqlUserRepository(session)
        ann, bob = (
            user_repository.add(User(name="ann")),
            user_repository.add(User(name="bob")),
        )
        bob.deactivate()
        user_repository.save(bob)
        users_service = users.UsersService(session)
        assert (
            users_service.is_active(ann.id)
            and not users_service.is_active(bob.id)
            and not users_service.is_active(999)
        )
