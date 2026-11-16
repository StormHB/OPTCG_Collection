"""Korak 11B.2B: preostale CRUD i konkurentne zastite kolekcije."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.models import Base, Card, CardPrinting, CardSet, CollectionEntry, User
from app.repositories import collection_repo
from app.routers.collections import router as collections_router
from app.schemas.collection import CollectionEntryCreate
from app.services import collection_service


def _client(user_id=7) -> TestClient:
    app = FastAPI()
    app.include_router(collections_router, prefix="/collections")
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=user_id, role="user", is_active=True
    )
    return TestClient(app)


def _entry(*, quantity=3, note="ostaje"):
    return SimpleNamespace(
        id=51,
        user_id=7,
        printing_id=13,
        quantity=quantity,
        note=note,
    )


def test_post_accepts_maximum_quantity_boundary():
    with (
        patch.object(
            collection_repo,
            "printing_exists",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(
            collection_repo,
            "get_for_user_and_printing",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch.object(
            collection_repo,
            "create_entry",
            new_callable=AsyncMock,
            return_value=_entry(quantity=999_999, note=None),
        ) as create,
    ):
        response = _client().post(
            "/collections/7/entries",
            json={"printing_id": 13, "quantity": 999_999},
        )
    assert response.status_code == 201, response.text
    assert response.json()["quantity"] == 999_999
    assert create.await_args.args[3] == 999_999


def test_unknown_other_user_path_is_forbidden_before_collection_query():
    with patch.object(
        collection_repo, "list_for_user", new_callable=AsyncMock
    ) as list_entries:
        response = _client(user_id=7).get("/collections/999999")
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    list_entries.assert_not_awaited()


def test_database_unique_constraint_rejects_duplicate_user_printing():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        card_set = CardSet(code="OP01", name="OP01", sort_order=1)
        card = Card(code="OP01-001", name="Test", original_set=card_set)
        printing = CardPrinting(card=card, product_set=card_set, variant_code="regular")
        user = User(username="owner_11b2b", password_hash="unused", role="user")
        session.add_all([printing, user])
        session.flush()
        session.add(
            CollectionEntry(user_id=user.id, printing_id=printing.id, quantity=1)
        )
        session.commit()

        session.add(
            CollectionEntry(user_id=user.id, printing_id=printing.id, quantity=2)
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

        count = session.scalar(select(func.count()).select_from(CollectionEntry))
        assert count == 1
    engine.dispose()


def test_service_maps_create_race_integrity_error_to_safe_409():
    error = IntegrityError("INSERT collection_entries", {}, Exception("unique"))
    with (
        patch.object(
            collection_repo,
            "printing_exists",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(
            collection_repo,
            "get_for_user_and_printing",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch.object(
            collection_repo,
            "create_entry",
            new_callable=AsyncMock,
            side_effect=error,
        ),
    ):
        with pytest.raises(AppError) as raised:
            asyncio.run(
                collection_service.add_collection_entry(
                    object(),
                    SimpleNamespace(id=7),
                    7,
                    CollectionEntryCreate(printing_id=13, quantity=1),
                )
            )
    assert raised.value.status_code == 409
    assert raised.value.code == "conflict"
    assert "unique" not in raised.value.message.lower()


class _LockRecordingDb:
    def __init__(self, scalar_result, events=None):
        self.scalar_result = scalar_result
        self.events = events if events is not None else []
        self.statements = []
        self.deleted = []

    async def scalar(self, statement):
        self.events.append("lock")
        self.statements.append(statement)
        return self.scalar_result

    async def flush(self):
        return None

    async def delete(self, entry):
        self.deleted.append(entry)


def _postgres_sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_quantity_patch_locks_collection_row_before_loan_check():
    entry = _entry(quantity=5)
    events = []
    db = _LockRecordingDb(entry, events)

    async def outstanding_lent(*_args):
        events.append("loans")
        return 3

    with patch(
        "app.repositories.collection_repo.card_loan_repo.outstanding_lent",
        new=AsyncMock(side_effect=outstanding_lent),
    ) as outstanding:
        updated = asyncio.run(collection_repo.update_entry(db, entry, {"quantity": 3}))
    assert updated.quantity == 3
    assert "FOR UPDATE" in _postgres_sql(db.statements[0])
    assert events == ["lock", "loans"]
    outstanding.assert_awaited_once_with(db, 7, 13)


def test_delete_locks_collection_row_before_active_loan_check():
    entry = _entry(quantity=5)
    events = []
    db = _LockRecordingDb(entry.id, events)

    async def outstanding_lent(*_args):
        events.append("loans")
        return 0

    with patch(
        "app.repositories.collection_repo.card_loan_repo.outstanding_lent",
        new=AsyncMock(side_effect=outstanding_lent),
    ) as outstanding:
        asyncio.run(collection_repo.delete_entry(db, entry))
    assert "FOR UPDATE" in _postgres_sql(db.statements[0])
    assert events == ["lock", "loans"]
    outstanding.assert_awaited_once_with(db, 7, 13)
    assert db.deleted == [entry]


def test_delete_returns_404_if_row_disappears_before_lock():
    entry = _entry(quantity=5)
    events = []
    db = _LockRecordingDb(None, events)
    with patch(
        "app.repositories.collection_repo.card_loan_repo.outstanding_lent",
        new_callable=AsyncMock,
    ) as outstanding:
        with pytest.raises(AppError) as raised:
            asyncio.run(collection_repo.delete_entry(db, entry))
    assert raised.value.status_code == 404
    assert raised.value.code == "not_found"
    assert events == ["lock"]
    outstanding.assert_not_awaited()
    assert db.deleted == []
