"""Korak 8A: HTTP pravila osobnih kolekcija bez PostgreSQL poslužitelja."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.repositories import collection_repo
from app.routers.collections import router as collections_router
from fastapi.exceptions import RequestValidationError


def make_client(user_id: int | None = 7, role: str = "user") -> TestClient:
    app = FastAPI()
    app.include_router(collections_router, prefix="/collections")
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    async def dummy_db():
        yield object()  # Stvarni repo zamijenjen je mock objektima.

    app.dependency_overrides[get_db] = dummy_db
    if user_id is not None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=user_id, role=role, is_active=True
        )
    else:
        async def unauthorized():
            raise AppError("invalid_credentials", "Nedostaje token", 401)
        app.dependency_overrides[get_current_user] = unauthorized
    return TestClient(app)


def fake_entry(quantity=3, note="moja karta"):
    return SimpleNamespace(id=51, user_id=7, printing_id=13, quantity=quantity, note=note)


def test_post_creates_entry_and_returns_201():
    client = make_client()
    with (
        patch.object(collection_repo, "printing_exists", new_callable=AsyncMock, return_value=True),
        patch.object(collection_repo, "get_for_user_and_printing", new_callable=AsyncMock, return_value=None),
        patch.object(collection_repo, "create_entry", new_callable=AsyncMock, return_value=fake_entry()) as create,
    ):
        response = client.post("/collections/7/entries", json={
            "printing_id": 13, "quantity": 3, "note": "moja karta"
        })
        assert response.status_code == 201
        assert response.json() == {"id": 51, "printing_id": 13, "quantity": 3, "note": "moja karta"}
        create.assert_awaited_once()
        assert create.await_args.args[1:] == (7, 13, 3, "moja karta")


def test_post_accepts_zero_quantity():
    client = make_client()
    with (
        patch.object(collection_repo, "printing_exists", new_callable=AsyncMock, return_value=True),
        patch.object(collection_repo, "get_for_user_and_printing", new_callable=AsyncMock, return_value=None),
        patch.object(collection_repo, "create_entry", new_callable=AsyncMock, return_value=fake_entry(quantity=0)) as create,
    ):
        response = client.post("/collections/7/entries", json={"printing_id": 13, "quantity": 0})
        assert response.status_code == 201
        assert response.json()["quantity"] == 0
        assert create.await_args.args[3] == 0


def test_post_rejects_duplicate_with_409():
    client = make_client()
    with (
        patch.object(collection_repo, "printing_exists", new_callable=AsyncMock, return_value=True),
        patch.object(collection_repo, "get_for_user_and_printing", new_callable=AsyncMock, return_value=fake_entry()),
        patch.object(collection_repo, "create_entry", new_callable=AsyncMock) as create,
    ):
        response = client.post("/collections/7/entries", json={"printing_id": 13, "quantity": 3})
        assert response.status_code == 409
        assert response.json()["code"] == "conflict"
        create.assert_not_awaited()


def test_post_nonexistent_printing_404():
    client = make_client()
    with (
        patch.object(collection_repo, "printing_exists", new_callable=AsyncMock, return_value=False),
        patch.object(collection_repo, "create_entry", new_callable=AsyncMock) as create,
    ):
        response = client.post("/collections/7/entries", json={"printing_id": 54321, "quantity": 3})
        assert response.status_code == 404
        create.assert_not_awaited()


@pytest.mark.parametrize("body", [
    {"printing_id": 13, "quantity": -1},
    {"printing_id": 0, "quantity": 2},
    {"printing_id": 13, "quantity": None},
    {"printing_id": 13, "quantity": 2, "note": "x" * 1001},
])
def test_post_invalid_data_returns_422(body):
    client = make_client()
    with patch.object(collection_repo, "create_entry", new_callable=AsyncMock) as create:
        response = client.post("/collections/7/entries", json=body)
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"
        create.assert_not_awaited()


@pytest.mark.parametrize("method,path,body", [
    ("post", "/collections/8/entries", {"printing_id": 13, "quantity": 2}),
    ("patch", "/collections/8/entries/13", {"quantity": 2}),
    ("delete", "/collections/8/entries/13", None),
])
def test_other_users_collection_is_forbidden(method, path, body):
    client = make_client(user_id=7, role="admin")
    with patch.object(collection_repo, "get_for_user_and_printing", new_callable=AsyncMock) as get_entry:
        response = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
        assert response.status_code == 403
        get_entry.assert_not_awaited()


def test_no_auth_returns_401():
    client = make_client(user_id=None)
    assert client.post("/collections/7/entries", json={"printing_id": 13, "quantity": 1}).status_code == 401


def test_patch_changes_only_provided_quantity():
    client = make_client()
    entry = fake_entry(quantity=3, note="ostaje")

    async def update(_db, existing, changes):
        for k, v in changes.items():
            setattr(existing, k, v)
        return existing

    with (
        patch.object(collection_repo, "get_for_user_and_printing", new_callable=AsyncMock, return_value=entry),
        patch.object(collection_repo, "update_entry", new=AsyncMock(side_effect=update)) as update_repo,
    ):
        response = client.patch("/collections/7/entries/13", json={"quantity": 4})
        assert response.status_code == 200
        assert response.json()["quantity"] == 4
        assert response.json()["note"] == "ostaje"
        assert update_repo.await_args.args[2] == {"quantity": 4}


def test_patch_explicit_null_removes_note():
    client = make_client()
    entry = fake_entry()

    async def update(_db, existing, changes):
        for k, v in changes.items():
            setattr(existing, k, v)
        return existing

    with (
        patch.object(collection_repo, "get_for_user_and_printing", new_callable=AsyncMock, return_value=entry),
        patch.object(collection_repo, "update_entry", new=AsyncMock(side_effect=update)) as update_repo,
    ):
        response = client.patch("/collections/7/entries/13", json={"note": None})
        assert response.status_code == 200
        assert response.json()["note"] is None
        assert update_repo.await_args.args[2] == {"note": None}


@pytest.mark.parametrize("body", [{}, {"quantity": None}, {"quantity": -2}])
def test_patch_invalid_body_422(body):
    client = make_client()
    with patch.object(collection_repo, "update_entry", new_callable=AsyncMock) as update:
        response = client.patch("/collections/7/entries/13", json=body)
        assert response.status_code == 422
        update.assert_not_awaited()


def test_patch_missing_entry_returns_404():
    client = make_client()
    with patch.object(collection_repo, "get_for_user_and_printing", new_callable=AsyncMock, return_value=None):
        response = client.patch("/collections/7/entries/13", json={"quantity": 2})
        assert response.status_code == 404


def test_delete_returns_204_and_no_body():
    client = make_client()
    with (
        patch.object(collection_repo, "get_for_user_and_printing", new_callable=AsyncMock, return_value=fake_entry()),
        patch.object(collection_repo, "delete_entry", new_callable=AsyncMock) as delete,
    ):
        response = client.delete("/collections/7/entries/13")
        assert response.status_code == 204
        assert response.content == b""
        delete.assert_awaited_once()


def test_delete_missing_entry_returns_404():
    client = make_client()
    with patch.object(collection_repo, "get_for_user_and_printing", new_callable=AsyncMock, return_value=None):
        assert client.delete("/collections/7/entries/13").status_code == 404
