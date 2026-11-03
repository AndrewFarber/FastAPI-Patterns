import pytest
from sqlalchemy.orm import Session

from app.services.users.domain.entities import User, UserStatus
from app.services.users.domain.errors import UserChangedError
from app.services.users.infrastructure.repositories import SqlUserRepository


def test_save_bumps_the_version(engine):
    with Session(engine) as session:
        user_repository = SqlUserRepository(session)
        ann = user_repository.add(User(name="ann"))
        assert ann.version == 1
        ann.deactivate()
        user_repository.save(ann)
        assert ann.version == 2 and user_repository.get(ann.id) == User(
            id=ann.id, name="ann", status=UserStatus.DEACTIVATED, version=2
        )


def test_save_of_a_stale_copy_is_a_conflict(engine):
    with Session(engine) as session, session.begin():
        ann_id = SqlUserRepository(session).add(User(name="ann")).id
    with Session(engine) as first, Session(engine) as second:
        mine, theirs = (
            SqlUserRepository(first).get(ann_id),
            SqlUserRepository(second).get(ann_id),
        )
        theirs.name = "anne"
        SqlUserRepository(second).save(theirs)
        second.commit()
        mine.deactivate()
        with pytest.raises(UserChangedError):
            SqlUserRepository(first).save(mine)
