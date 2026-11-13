"""HTTP i servisna pravila posudbi bez testiranja na privatnoj PostgreSQL bazi."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.repositories import card_loan_repo
from app.routers.collections import router as collections_router

STAMP = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def make_client(user_id: int | None = 7, role: str = "user") -> TestClient:
    app = FastAPI()
    app.include_router(collections_router, prefix="/collections")
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    async def fake_db():
        yield object()

    async def fake_user():
        if user_id is None:
            raise AppError("invalid_credentials", "Nedostaje access token", 401)
        return SimpleNamespace(id=user_id, role=role, is_active=True)

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = fake_user
    return TestClient(app)


def loan_stub(*, direction="lent", quantity=5, returned=0, loan_id=77):
    return SimpleNamespace(
        id=loan_id, user_id=7, printing_id=13, direction=direction,
        person_name="Ivan", quantity=quantity, quantity_returned=returned,
        loaned_at=STAMP, due_at=STAMP + timedelta(days=7),
        returned_at=None, note="test",
        printing=SimpleNamespace(
            card=SimpleNamespace(code="OP01-016", name="Nami"),
            product_set=SimpleNamespace(code="OP01"),
            variant_code="regular", image_url="https://example.org/nami.png",
        ),
    )


def payload(**changes):
    result = {
        "printing_id": 13, "direction": "lent", "person_name": " Ivan ",
        "quantity": 2, "loaned_at": "2026-11-10T13:00:00+01:00",
        "due_at": "2026-11-17T12:00:00Z",
    }
    result.update(changes)
    return result


def loan_mocks(*, owned=5, outstanding=3, loaded=None, exists=True):
    """Mijenja samo repo: izbjegava stvarni DB, ali izvršava HTTP i servisnu logiku."""
    if loaded is None:
        loaded = loan_stub()
    async def add(_db, loan):
        loan.id = 77
        return loan
    return (
        patch.object(card_loan_repo, "printing_exists", new_callable=AsyncMock, return_value=exists),
        patch.object(card_loan_repo, "owned_quantity_locked", new_callable=AsyncMock, return_value=owned),
        patch.object(card_loan_repo, "outstanding_lent", new_callable=AsyncMock, return_value=outstanding),
        patch.object(card_loan_repo, "create", new_callable=AsyncMock, side_effect=add),
        patch.object(card_loan_repo, "get_for_owner", new_callable=AsyncMock, return_value=loaded),
    )


def test_create_lent_success_201_and_exact_printing():
    with (
        loan_mocks()[0] as exists,
        loan_mocks()[1] as owned,
        loan_mocks()[2] as outstanding,
        loan_mocks()[3] as add,
        loan_mocks()[4] as read,
    ):
        response = make_client().post("/collections/7/loans", json=payload())
        assert response.status_code == 201, response.text
        doc = response.json()
        assert doc["printing_id"] == 13
        assert doc["card_code"] == "OP01-016"
        assert doc["set_code"] == "OP01"
        assert doc["image_url"] == "https://example.org/nami.png"
        assert doc["outstanding_quantity"] == 5
        assert owned.await_args.args[1:] == (7, 13)
        assert outstanding.await_args.args[1:] == (7, 13)
        assert add.await_args.args[1].person_name == "Ivan"
        assert add.await_args.args[1].loaned_at == STAMP
        exists.assert_awaited_once()
        read.assert_awaited_once()


def test_create_lent_insufficient_quantity_409_and_no_write():
    mocks = loan_mocks(owned=5, outstanding=4)
    with (mocks[0], mocks[1], mocks[2], mocks[3] as add, mocks[4]):
        response = make_client().post("/collections/7/loans", json=payload(quantity=2))
        assert response.status_code == 409
        assert response.json() == {
            "code": "insufficient_quantity",
            "message": "Nije moguce posuditi 2 primjeraka; dostupno je 1",
        }
        add.assert_not_awaited()


def test_create_borrowed_does_not_use_owned_cards():
    mocks = loan_mocks(owned=0, outstanding=0, loaded=loan_stub(direction="borrowed"))
    with (mocks[0], mocks[1] as owned, mocks[2] as lent, mocks[3] as create, mocks[4]):
        response = make_client().post("/collections/7/loans", json=payload(direction="borrowed", quantity=50))
        assert response.status_code == 201, response.text
        assert response.json()["direction"] == "borrowed"
        owned.assert_not_awaited()
        lent.assert_not_awaited()
        create.assert_awaited_once()


def test_create_unknown_printing_404():
    mocks = loan_mocks(exists=False)
    with (mocks[0], mocks[1], mocks[2], mocks[3] as create, mocks[4]):
        response = make_client().post("/collections/7/loans", json=payload())
        assert response.status_code == 404
        assert response.json()["code"] == "printing_not_found"
        create.assert_not_awaited()


@pytest.mark.parametrize("changes", [
    {"printing_id": 0}, {"direction": "gifted"}, {"person_name": "   "},
    {"quantity": 0}, {"quantity": -1}, {"quantity": 1_000_000},
    {"loaned_at": "2026-11-10T10:00:00"}, # naive date
    {"due_at": "2026-11-10T10:00:00"}, # naive date
])
def test_create_rejects_invalid_schema_before_db(changes):
    mocks = loan_mocks()
    with (mocks[0] as exists, mocks[1], mocks[2], mocks[3] as create, mocks[4]):
        response = make_client().post("/collections/7/loans", json=payload(**changes))
        assert response.status_code == 422, (changes, response.text)
        assert response.json()["code"] == "validation_error"
        create.assert_not_awaited()
        exists.assert_not_awaited()


def test_create_rejects_due_before_loaned_422():
    mocks = loan_mocks()
    with (mocks[0] as exists, mocks[1], mocks[2], mocks[3] as create, mocks[4]):
        response = make_client().post("/collections/7/loans", json=payload(
            due_at="2026-11-09T12:00:00Z"
        ))
        assert response.status_code == 422
        assert response.json()["code"] == "invalid_loan_dates"
        assert create.await_count == 0
        exists.assert_not_awaited()


def test_create_denies_other_owner_even_admin_and_does_not_read_database():
    mocks = loan_mocks()
    with (mocks[0] as exists, mocks[1], mocks[2], mocks[3] as create, mocks[4]):
        response = make_client(user_id=7, role="admin").post("/collections/8/loans", json=payload())
        assert response.status_code == 403
        assert response.json()["code"] == "forbidden"
        exists.assert_not_awaited()
        create.assert_not_awaited()


def test_no_login_401():
    assert make_client(user_id=None).post("/collections/7/loans", json=payload()).status_code == 401


def test_list_filter_direction_and_active_only():
    with patch.object(card_loan_repo, "list_for_owner", new_callable=AsyncMock,
                      return_value=[loan_stub(returned=2)]) as read:
        response = make_client().get("/collections/7/loans?direction=lent&active_only=true")
        assert response.status_code == 200
        assert response.json()[0]["outstanding_quantity"] == 3
        assert read.await_args.kwargs == {"direction": "lent", "active_only": True}


def test_list_invalid_direction_422():
    assert make_client().get("/collections/7/loans?direction=lost").status_code == 422


def test_list_other_user_403_without_query():
    with patch.object(card_loan_repo, "list_for_owner", new_callable=AsyncMock) as read:
        response = make_client().get("/collections/8/loans")
        assert response.status_code == 403
        read.assert_not_awaited()


def test_read_loan_and_404():
    with patch.object(card_loan_repo, "get_for_owner", new_callable=AsyncMock,
                      return_value=loan_stub()) as read:
        response = make_client().get("/collections/7/loans/77")
        assert response.status_code == 200
        assert read.await_args.args[1:] == (7, 77)
    with patch.object(card_loan_repo, "get_for_owner", new_callable=AsyncMock, return_value=None):
        response = make_client().get("/collections/7/loans/77")
        assert response.status_code == 404
        assert response.json()["code"] == "loan_not_found"


def test_partial_return_200_and_no_completed_date():
    loan = loan_stub(quantity=5, returned=1)
    with (patch.object(card_loan_repo, "get_for_owner", new_callable=AsyncMock,
                       return_value=loan) as read,
          patch.object(card_loan_repo, "flush", new_callable=AsyncMock) as flush):
        response = make_client().post("/collections/7/loans/77/returns", json={
            "quantity": 2, "returned_at": "2026-11-12T13:00:00+01:00"
        })
        assert response.status_code == 200, response.text
        assert response.json()["quantity_returned"] == 3
        assert response.json()["outstanding_quantity"] == 2
        assert response.json()["returned_at"] is None
        assert read.await_args.kwargs == {"lock": True}
        flush.assert_awaited_once()


def test_final_return_sets_utc_date():
    loan = loan_stub(quantity=5, returned=3)
    with (patch.object(card_loan_repo, "get_for_owner", new_callable=AsyncMock, return_value=loan),
          patch.object(card_loan_repo, "flush", new_callable=AsyncMock)):
        response = make_client().post("/collections/7/loans/77/returns", json={
            "quantity": 2, "returned_at": "2026-11-12T13:00:00+01:00"
        })
        assert response.status_code == 200
        assert response.json()["quantity_returned"] == 5
        assert response.json()["outstanding_quantity"] == 0
        assert response.json()["returned_at"] == "2026-11-12T12:00:00Z"


@pytest.mark.parametrize("already,requested,code", [
    (2, 4, "return_exceeds_outstanding"),
    (5, 1, "loan_already_returned"),
])
def test_invalid_return_409_no_write(already, requested, code):
    loan = loan_stub(quantity=5, returned=already)
    with (patch.object(card_loan_repo, "get_for_owner", new_callable=AsyncMock, return_value=loan),
          patch.object(card_loan_repo, "flush", new_callable=AsyncMock) as flush):
        response = make_client().post("/collections/7/loans/77/returns", json={"quantity": requested})
        assert response.status_code == 409
        assert response.json()["code"] == code
        assert loan.quantity_returned == already
        flush.assert_not_awaited()


def test_missing_loan_return_404():
    with patch.object(card_loan_repo, "get_for_owner", new_callable=AsyncMock, return_value=None):
        response = make_client().post("/collections/7/loans/77/returns", json={"quantity": 1})
        assert response.status_code == 404


def test_return_date_before_loan_422_and_no_write():
    loan = loan_stub()
    with (patch.object(card_loan_repo, "get_for_owner", new_callable=AsyncMock, return_value=loan),
          patch.object(card_loan_repo, "flush", new_callable=AsyncMock) as flush):
        response = make_client().post("/collections/7/loans/77/returns", json={
            "quantity": 1, "returned_at": "2026-11-09T10:00:00Z"
        })
        assert response.status_code == 422
        assert response.json()["code"] == "invalid_return_date"
        flush.assert_not_awaited()


@pytest.mark.parametrize("body", [{"quantity": 0}, {"quantity": -1},
                                   {"quantity": 1, "returned_at": "2026-11-12T15:30:00"}])
def test_return_schema_rejects_bad_input(body):
    with patch.object(card_loan_repo, "get_for_owner", new_callable=AsyncMock) as read:
        response = make_client().post("/collections/7/loans/77/returns", json=body)
        assert response.status_code == 422
        read.assert_not_awaited()


@pytest.mark.parametrize("method,path,json", [
    ("get", "/collections/8/loans/77", None),
    ("post", "/collections/8/loans/77/returns", {"quantity": 1}),
])
def test_other_user_cannot_read_or_return(method, path, json):
    with patch.object(card_loan_repo, "get_for_owner", new_callable=AsyncMock) as read:
        client = make_client(user_id=7, role="admin")
        response = getattr(client, method)(path, json=json) if json else getattr(client, method)(path)
        assert response.status_code == 403
        read.assert_not_awaited()


def test_loan_repository_uses_for_update_when_lending():
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.sql import Select

    class FakeDB:
        statement = None
        async def scalar(self, statement):
            self.statement = statement
            return 5

    db = FakeDB()
    import asyncio
    assert asyncio.run(card_loan_repo.owned_quantity_locked(db, 7, 13)) == 5
    sql = str(db.statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    assert "collection_entries" in sql
