---
title: "Naming"
category: conventions
related:
  - "[[naming-guide]]"
  - "[[naming-domain]]"
  - "[[naming-infrastructure]]"
  - "[[naming-api]]"
---

# Naming

## Overview
One way to name each kind of thing, so a name says what it holds or does and a reader can guess the name of what they're looking for. The layer notes ([[naming-domain]], [[naming-infrastructure]], [[naming-api]]) build on these rules.

## Rules
- **Modules:** `snake_case`; plural when the module holds many things of one kind (`entities.py`, `repositories.py`, `use_cases/`), singular when it is one thing or one concern (`router.py`, `outbox/`). Name a module after its technology only when another could replace it (`messaging/sns.py`). Base types go in `base.py`.
- **Errors, not exceptions:** modules and packages that hold error types are `errors` (`domain/errors.py`, `shared/errors/`, `core/errors/`), matching the class names.
- **Functions start with a verb.** A pure conversion is `to_<target>` / `from_<source>`.
- **Factory verbs:** `create_` builds a new object (`create_app`, `create_engine`, `create_sns_sender`); `get_` returns an existing or computed one (`get_settings`, `get_connect_args`, `get_event_name`) and names every `Depends()` provider. A name that shadows a library's is fine when the library is imported as a module: `sa.create_engine` inside our `create_engine`.
- **Collaborators are named after their type:** `order_repository: OrderRepository`, `user_directory: UserDirectory`, `unit_of_work: UnitOfWorkDep`, never `repo`, `uow`, or `orders`. A generic type is named after what it holds: `parameters: TtlCache`, `session: Session`.
- **No abbreviations** except well-known ones (`db`, `id`, `url`, `aws`, `sns`). A single letter only inside a one-line comprehension: `[o.status for o in orders]`.
- **Booleans read as yes/no:** `is_`, `has_`, `can_` (`is_active()`, `is_ordering_paused()`). Settings fields that mirror a library's option keep its name (`debug`, `echo`, `allow_credentials`); a feature flag is named after the feature (`features.new_checkout`).
- **Durations are `timedelta`** in functions and classes (`TtlCache(fetch, ttl=...)`, `Workers.retention`). Settings fields are numbers with the unit in the name (`ttl_seconds`, `retention_days`), converted once where they're passed in; a bare number in an env var would otherwise be read as seconds.
- **Constants are `UPPER_CASE`** and say what maps to what (`STATUS_CODES`, `CLIENT_CONFIG`). Module-level objects with behavior stay lowercase: `logger`, `router`, `app`, `workers`.
- **Private is one `_`:** for anything not used outside its module or class; never `__`. Tests use public names only.
- **Tests:**
  - **Files mirror `app/`** one module to one file: `app/core/db/engine.py` → `tests/core/db/test_engine.py`. A flow through the whole app goes in `tests/test_main.py`.
  - **Names are sentences:** `test_<subject>_<behavior>`, `test_save_of_a_stale_copy_is_a_conflict`, never a bare noun like `test_cors`.
  - **Fakes are `Fake<Protocol>`:** `FakeOrderRepository`, `FakeEventPublisher`; shared fakes live in a `fakes.py` next to the tests that use them.
  - **Fixtures:** a noun for a value (`engine`, `client`), `create_` for a factory (`create_app`). A fixture used only for its side effect names the state it sets up (`test_env`, `clean_env`, `aws_credentials`), or what it puts back when it undoes a change (`restore_logging`). A helper that isn't a fixture follows the function rules: `create_test_env()`.
- **`ruff` checks the casing** and the `Error` suffix (pep8-naming, `N`); the rest is review.

## Code example

| Kind | Name | Not |
| --- | --- | --- |
| Module of many | `repositories.py`, `use_cases/` | `repository.py` |
| Module of one | `router.py`, `unit_of_work.py` | `routers.py` |
| Factory | `create_engine(db, application_name)` | `build_engine`, `make_engine` |
| Getter | `get_settings()`, `get_order_repository(...)` | `settings()` |
| Collaborator | `order_repository: OrderRepository` | `repo`, `orders` |
| Boolean | `is_ordering_paused()` | `ordering_paused()` |
| Duration | `ttl: timedelta`; setting `ttl_seconds: float` | `ttl: float` |
| Constant | `STATUS_CODES: dict[type[DomainError], int]` | `STATUS` |
| Test | `test_deactivate_unknown_user_is_not_found` | `test_deactivate_unknown_user` |
| Fake | `FakeMessageSender` | `RecordingSender` |

```
app/core/db/engine.py                         tests/core/db/test_engine.py
app/core/db/iam_auth.py                       tests/core/db/test_iam_auth.py
app/services/orders/use_cases/place_order.py  tests/services/orders/use_cases/test_place_order.py
                                              tests/services/orders/fakes.py
app/main.py                                   tests/test_main.py
```
