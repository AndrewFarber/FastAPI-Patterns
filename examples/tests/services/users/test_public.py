from sqlalchemy.orm import Session

from app.services import users
from app.services.users.domain.entities import User
from app.services.users.infrastructure.repositories import SqlUserRepository


def test_is_active_applies_the_users_rule(engine):
    with Session(engine) as session:
        repo = SqlUserRepository(session)
        ann, bob = repo.add(User(name="ann")), repo.add(User(name="bob"))
        bob.deactivate()
        repo.save(bob)
        api = users.UsersApi(session)
        assert (
            api.is_active(ann.id)
            and not api.is_active(bob.id)
            and not api.is_active(999)
        )
