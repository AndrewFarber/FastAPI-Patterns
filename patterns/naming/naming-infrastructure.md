---
title: "Naming: infrastructure"
category: conventions
related:
  - "[[naming-guide]]"
  - "[[naming]]"
  - "[[naming-domain]]"
  - "[[layout]]"
  - "[[services-events]]"
---

# Naming: infrastructure

## Overview
Names in a service's `infrastructure/` and in the database, building on [[naming]]. ORM classes never share a name with the entities they store, tables read like SQL, and every constraint has a predictable name that migrations can refer to.

## Rules
- **ORM classes are `Db<Entity>`:** `DbOrder`, `DbUser`, `DbOutboxEvent`, `DbProcessedEvent`, named after what one row is. `Order` stays free for the entity, and a `Db` class never crosses into the domain.
- **Tables are the plural of what one row is,** in the owning service's schema ([[layout]]): `orders.orders`, `users.users`, `events.processed_events`. A plural avoids reserved words like `user` and `order`, which singular tables would have to quote in every hand-written query. A well-known pattern name stays as it is: `events.outbox`.
- **Columns are `snake_case` nouns;** foreign keys are `<entity>_id` (`user_id`), timestamps are `<past_verb>_at` (`created_at`, `sent_at`).
- **Constraint names come from a naming convention** on `Base.metadata`, so every index, key, and check has a deterministic name across databases and migrations. Name a constraint by hand only when the convention can't express it, like a partial index: `ix_outbox_pending`.
- **Map rows to entities with `to_entity(row)`,** a module function next to the repository that uses it. Writes list their columns where they write: `add` builds a new `DbOrder`, `save` issues a versioned `UPDATE`, and neither needs a reverse mapper.
- **Implementations put their technology first** ([[naming-domain]]): `SqlOrderRepository`, `SsmOrderSwitches`.

## Code example
```python
# app/core/db/base.py
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
```

```python
# app/services/orders/infrastructure/models.py
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base


class DbOrder(Base):
    __tablename__ = "orders"
    __table_args__ = {"schema": "orders"}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    item: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(default=1)
```
