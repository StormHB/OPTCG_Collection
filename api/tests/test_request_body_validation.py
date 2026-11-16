"""Korak 11A.2: nepoznata polja i strogi tipovi ne smiju doci do servisa."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.routers.auth import router as auth_router
from app.routers.collections import router as collections_router
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest
from app.schemas.card_loan import CardLoanCreate, CardLoanReturn
from app.schemas.collection import CollectionEntryCreate, CollectionEntryUpdate
from app.services import auth_service, card_loan_service, collection_service


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(collections_router, prefix="/collections")
    app.include_router(auth_router, prefix="/auth")
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7, role="user", is_active=True
    )
    return TestClient(app)


VALID_ENTRY = {"printing_id": 13, "quantity": 2}
VALID_LOAN = {
    "printing_id": 13,
    "direction": "lent",
    "person_name": "Nami",
    "quantity": 2,
}


@pytest.mark.parametrize(
    "payload,field",
    [
        ({**VALID_ENTRY, "quantitty": 5}, "quantitty"),
        ({**VALID_ENTRY, "unexpected": None}, "unexpected"),
        ({**VALID_ENTRY, "quantity": "2"}, "quantity"),
        ({**VALID_ENTRY, "quantity": 2.0}, "quantity"),
        ({**VALID_ENTRY, "quantity": True}, "quantity"),
        ({**VALID_ENTRY, "quantity": -1}, "quantity"),
        ({**VALID_ENTRY, "quantity": 1_000_000}, "quantity"),
        ({**VALID_ENTRY, "printing_id": "13"}, "printing_id"),
        ({**VALID_ENTRY, "printing_id": 0}, "printing_id"),
        ({**VALID_ENTRY, "note": ""}, "note"),
        ({**VALID_ENTRY, "note": "  \t"}, "note"),
        ({**VALID_ENTRY, "note": 123}, "note"),
        ({**VALID_ENTRY, "note": "x" * 1001}, "note"),
    ],
)
def test_create_entry_rejects_invalid_body_before_service(payload, field):
    with patch.object(
        collection_service, "add_collection_entry", new_callable=AsyncMock
    ) as add:
        result = make_client().post("/collections/7/entries", json=payload)
    assert result.status_code == 422, result.text
    body = result.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "Neispravni podaci u zahtjevu"
    assert any(error["field"] == field for error in body["errors"])
    add.assert_not_awaited()


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"quantitty": 3}, "quantitty"),
        ({"quantity": 2, "debug": True}, "debug"),
        ({"quantity": "2"}, "quantity"),
        ({"quantity": 2.0}, "quantity"),
        ({"quantity": False}, "quantity"),
        ({"quantity": None}, ""),
        ({"quantity": -1}, "quantity"),
        ({"quantity": 1_000_000}, "quantity"),
        ({"note": ""}, "note"),
        ({"note": "  "}, "note"),
        ({"note": 13}, "note"),
    ],
)
def test_patch_entry_rejects_invalid_body_before_service(payload, field):
    with patch.object(
        collection_service, "update_collection_entry", new_callable=AsyncMock
    ) as update:
        result = make_client().patch("/collections/7/entries/13", json=payload)
    assert result.status_code == 422, result.text
    assert result.json()["code"] == "validation_error"
    if field:
        assert any(error["field"] == field for error in result.json()["errors"])
    update.assert_not_awaited()


@pytest.mark.parametrize(
    "payload,field",
    [
        ({**VALID_LOAN, "unknown": "ignored?"}, "unknown"),
        ({**VALID_LOAN, "quantitty": 5}, "quantitty"),
        ({**VALID_LOAN, "printing_id": "13"}, "printing_id"),
        ({**VALID_LOAN, "quantity": "2"}, "quantity"),
        ({**VALID_LOAN, "quantity": 2.0}, "quantity"),
        ({**VALID_LOAN, "quantity": True}, "quantity"),
        ({**VALID_LOAN, "quantity": 0}, "quantity"),
        ({**VALID_LOAN, "quantity": 1_000_000}, "quantity"),
        ({**VALID_LOAN, "person_name": " "}, "person_name"),
        ({**VALID_LOAN, "person_name": 12}, "person_name"),
        ({**VALID_LOAN, "direction": "gifted"}, "direction"),
        ({**VALID_LOAN, "note": "  "}, "note"),
        ({**VALID_LOAN, "note": 7}, "note"),
        ({**VALID_LOAN, "loaned_at": "2026-11-10T12:00:00"}, "loaned_at"),
        ({**VALID_LOAN, "loaned_at": 1794326400}, "loaned_at"),
        ({**VALID_LOAN, "due_at": 1794326400}, "due_at"),
    ],
)
def test_create_loan_rejects_invalid_body_before_service(payload, field):
    with patch.object(
        card_loan_service, "create_loan", new_callable=AsyncMock
    ) as create:
        result = make_client().post("/collections/7/loans", json=payload)
    assert result.status_code == 422, result.text
    assert result.json()["code"] == "validation_error"
    assert any(error["field"] == field for error in result.json()["errors"])
    create.assert_not_awaited()


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"quantity": 1, "returnned_at": "2026-11-11T00:00:00Z"}, "returnned_at"),
        ({"quantity": "1"}, "quantity"),
        ({"quantity": 1.0}, "quantity"),
        ({"quantity": True}, "quantity"),
        ({"quantity": None}, "quantity"),
        ({"quantity": 0}, "quantity"),
        ({"quantity": -1}, "quantity"),
        ({"quantity": 1_000_000}, "quantity"),
        ({"quantity": 1, "returned_at": "2026-11-11T12:00:00"}, "returned_at"),
        ({"quantity": 1, "returned_at": 1794326400}, "returned_at"),
    ],
)
def test_return_loan_rejects_invalid_body_before_service(payload, field):
    with patch.object(
        card_loan_service, "return_loan", new_callable=AsyncMock
    ) as return_loan:
        result = make_client().post("/collections/7/loans/22/returns", json=payload)
    assert result.status_code == 422, result.text
    assert result.json()["code"] == "validation_error"
    assert any(error["field"] == field for error in result.json()["errors"])
    return_loan.assert_not_awaited()


@pytest.mark.parametrize(
    "path,payload,service,method",
    [
        (
            "/auth/register",
            {"username": "luffy", "password": "password123", "role": "admin"},
            "register_user",
            "post",
        ),
        (
            "/auth/login",
            {"username": "luffy", "password": "password123", "role": "admin"},
            "authenticate_user",
            "post",
        ),
        (
            "/auth/refresh",
            {"refresh_token": "token", "access_token": "unused"},
            "refresh_tokens",
            "post",
        ),
    ],
)
def test_auth_endpoints_reject_extra_fields(path, payload, service, method):
    with patch.object(auth_service, service, new_callable=AsyncMock) as handler:
        result = getattr(make_client(), method)(path, json=payload)
    assert result.status_code == 422, result.text
    assert result.json()["code"] == "validation_error"
    handler.assert_not_awaited()


def test_all_request_models_reject_unknown_fields_even_outside_http():
    valid = (
        (CollectionEntryCreate, VALID_ENTRY),
        (CollectionEntryUpdate, {"quantity": 3}),
        (CardLoanCreate, VALID_LOAN),
        (CardLoanReturn, {"quantity": 1}),
        (RegisterRequest, {"username": "luffy", "password": "password123"}),
        (LoginRequest, {"username": "luffy", "password": "password123"}),
        (RefreshRequest, {"refresh_token": "token"}),
    )
    for schema, payload in valid:
        with pytest.raises(ValidationError):
            schema.model_validate({**payload, "unsupported": "value"})


def test_patch_null_note_still_clears_and_missing_fields_stay_missing():
    data = CollectionEntryUpdate.model_validate({"note": None})
    assert data.model_dump(exclude_unset=True) == {"note": None}
    data = CollectionEntryUpdate.model_validate({"quantity": 0})
    assert data.model_dump(exclude_unset=True) == {"quantity": 0}


def test_optional_nulls_and_timezone_aware_dates_still_work():
    entry = CollectionEntryCreate.model_validate({**VALID_ENTRY, "note": None})
    assert entry.note is None
    loan = CardLoanCreate.model_validate(
        {
            **VALID_LOAN,
            "note": None,
            "loaned_at": "2026-11-10T13:00:00+01:00",
            "due_at": "2026-11-17T12:00:00Z",
        }
    )
    assert loan.loaned_at.utcoffset().total_seconds() == 3600
    returned = CardLoanReturn.model_validate(
        {"quantity": 1, "returned_at": "2026-11-10T13:00:00+01:00"}
    )
    assert returned.returned_at.utcoffset().total_seconds() == 3600


def test_post_and_patch_valid_ints_reach_service():
    # Validacija se obavlja prije servisa, bez baze i bez uplitanja u poslovnu logiku.
    entry = SimpleNamespace(id=1, printing_id=13, quantity=0, note=None)
    with patch.object(
        collection_service,
        "add_collection_entry",
        new_callable=AsyncMock,
        return_value=entry,
    ) as add:
        response = make_client().post(
            "/collections/7/entries", json={**VALID_ENTRY, "quantity": 0}
        )
    assert response.status_code == 201, response.text
    assert add.await_args.args[3].quantity == 0

    with patch.object(
        collection_service,
        "update_collection_entry",
        new_callable=AsyncMock,
        return_value=entry,
    ) as update:
        response = make_client().patch("/collections/7/entries/13", json={"note": None})
    assert response.status_code == 200, response.text
    assert update.await_args.args[4].model_dump(exclude_unset=True) == {"note": None}
