"""Korak 10A: HTTP, autentikacija, autorizacija i shape odgovora."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.repositories import collection_stats_repo
from app.routers.collections import router as collections_router


def client(user_id=7, role="user") -> TestClient:
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


def test_stats_get_200_exact_values_and_own_scope():
    rows = [
        (4, "Character", "R", "OP01", "OP01-016"),
        (1, None, "L", "OP01", "OP01-001"),
        (10, None, None, "DON", "DON-001"),
        (3, "Event", "C", "OP01", "OP01-023"),
    ]
    with patch.object(
        collection_stats_repo,
        "load_owned_printings",
        new_callable=AsyncMock,
        return_value=rows,
    ) as load:
        res = client().get("/collections/7/stats")
        assert res.status_code == 200, res.text
        assert res.json() == {
            "user_id": 7,
            "total_cards": 18,
            "distinct_printings": 4,
            "playsets": 3,
            "playsets_by_type": {"leader": 1, "don": 1, "other": 1},
        }
        load.assert_awaited_once()
        assert load.await_args.args[1] == 7


@pytest.mark.parametrize("role", ["user", "admin"])
def test_stats_other_user_403_without_database_query(role):
    with patch.object(
        collection_stats_repo, "load_owned_printings", new_callable=AsyncMock
    ) as load:
        res = client(7, role=role).get("/collections/8/stats")
        assert res.status_code == 403
        assert res.json() == {
            "code": "forbidden",
            "message": "Nemate pristup tudoj kolekciji",
        }
        load.assert_not_awaited()


def test_stats_no_auth_returns_401_without_database_query():
    with patch.object(
        collection_stats_repo, "load_owned_printings", new_callable=AsyncMock
    ) as load:
        res = client(None).get("/collections/7/stats")
        assert res.status_code == 401
        assert res.json()["code"] == "invalid_credentials"
        load.assert_not_awaited()


@pytest.mark.parametrize("invalid_id", [0, -1, "tekst"])
def test_stats_invalid_user_id_is_422(invalid_id):
    with patch.object(
        collection_stats_repo, "load_owned_printings", new_callable=AsyncMock
    ) as load:
        res = client().get(f"/collections/{invalid_id}/stats")
        assert res.status_code == 422
        assert res.json()["code"] == "validation_error"
        load.assert_not_awaited()


def test_stats_empty_collection_is_valid_and_read_only():
    with patch.object(
        collection_stats_repo,
        "load_owned_printings",
        new_callable=AsyncMock,
        return_value=[],
    ) as load:
        res = client().get("/collections/7/stats")
        assert res.status_code == 200
        assert res.json() == {
            "user_id": 7,
            "total_cards": 0,
            "distinct_printings": 0,
            "playsets": 0,
            "playsets_by_type": {"leader": 0, "don": 0, "other": 0},
        }
        load.assert_awaited_once()


def test_stats_does_not_have_post_or_patch_methods():
    # Tuđa izmjena kroz stats endpoint ne postoji.
    with patch.object(
        collection_stats_repo, "load_owned_printings", new_callable=AsyncMock
    ) as load:
        api = client()
        assert api.post("/collections/7/stats", json={}).status_code == 405
        assert api.patch("/collections/7/stats", json={}).status_code == 405
        load.assert_not_awaited()
