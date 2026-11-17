"""Korak 11B.2A: JWT, uloge i vlasnistvo bez stvarne korisnicke baze."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.deps import get_db
from app.core.jwt import ALGORITHM, create_access_token, create_refresh_token
from app.main import create_app
from app.repositories import admin_repo, card_repo, collection_repo, user_repo


def _user(user_id=7, *, role="user", active=True, password_hash="safe-hash"):
    return SimpleNamespace(
        id=user_id,
        username=f"user_{user_id}",
        password_hash=password_hash,
        role=role,
        is_active=active,
    )


def _client() -> TestClient:
    app = create_app()

    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    return TestClient(app)


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _expired_token(*, token_type="access", user_id=7) -> str:
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iss": settings.JWT_ISSUER,
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    if token_type == "access":
        payload["role"] = "user"
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "password": "password123"},
        {"username": "invalid-name", "password": "password123"},
        {"username": "valid_name", "password": "short"},
        {"username": 123, "password": "password123"},
        {"username": "valid_name", "password": "password123", "role": "admin"},
    ],
)
def test_invalid_registration_never_reaches_service(payload):
    with patch(
        "app.routers.auth.auth_service.register_user", new_callable=AsyncMock
    ) as register:
        response = _client().post("/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    register.assert_not_awaited()


def test_valid_registration_hashes_password_and_never_returns_it():
    created = _user()

    async def create(_db, user):
        user.id = created.id
        user.is_active = True
        return user

    with (
        patch.object(
            user_repo, "get_by_username", new_callable=AsyncMock, return_value=None
        ),
        patch.object(
            user_repo, "create", new=AsyncMock(side_effect=create)
        ) as create_user,
        patch(
            "app.services.auth_service.hash_password",
            return_value="bcrypt-secret-hash",
        ) as hash_password,
    ):
        response = _client().post(
            "/auth/register",
            json={"username": "valid_name", "password": "password123"},
        )
    assert response.status_code == 201, response.text
    assert response.json() == {
        "id": 7,
        "username": "valid_name",
        "role": "user",
        "is_active": True,
    }
    assert "password" not in response.text.lower()
    assert "bcrypt-secret-hash" not in response.text
    hash_password.assert_called_once_with("password123")
    created_user = create_user.await_args.args[1]
    assert created_user.password_hash == "bcrypt-secret-hash"
    assert created_user.role == "user"


def test_duplicate_username_returns_safe_409_without_write():
    with (
        patch.object(
            user_repo, "get_by_username", new_callable=AsyncMock, return_value=_user()
        ),
        patch.object(user_repo, "create", new_callable=AsyncMock) as create_user,
    ):
        response = _client().post(
            "/auth/register",
            json={"username": "user_7", "password": "password123"},
        )
    assert response.status_code == 409
    assert response.json() == {
        "code": "username_taken",
        "message": "Korisnicko ime je zauzeto",
    }
    assert "password" not in response.text.lower()
    assert "hash" not in response.text.lower()
    create_user.assert_not_awaited()


@pytest.mark.parametrize(
    "database_user,password_ok",
    [(_user(), False), (_user(active=False), True), (None, False)],
)
def test_login_rejects_wrong_password_inactive_and_missing_user_without_tokens(
    database_user, password_ok
):
    with (
        patch.object(
            user_repo,
            "get_by_username",
            new_callable=AsyncMock,
            return_value=database_user,
        ),
        patch("app.services.auth_service.verify_password", return_value=password_ok),
    ):
        response = _client().post(
            "/auth/login", json={"username": "user_7", "password": "wrong-value"}
        )
    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_credentials",
        "message": "Neispravno korisnicko ime ili lozinka",
    }
    assert "wrong-value" not in response.text
    assert "private-hash" not in response.text
    assert "token" not in response.text.lower()


def test_login_returns_distinct_access_and_refresh_tokens_with_correct_purpose():
    user = _user()
    with (
        patch.object(
            user_repo, "get_by_username", new_callable=AsyncMock, return_value=user
        ),
        patch("app.services.auth_service.verify_password", return_value=True),
    ):
        response = _client().post(
            "/auth/login", json={"username": "user_7", "password": "password123"}
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] != body["refresh_token"]
    assert (
        jwt.decode(
            body["access_token"],
            settings.JWT_SECRET,
            algorithms=[ALGORITHM],
            issuer=settings.JWT_ISSUER,
        )["type"]
        == "access"
    )
    assert (
        jwt.decode(
            body["refresh_token"],
            settings.JWT_SECRET,
            algorithms=[ALGORITHM],
            issuer=settings.JWT_ISSUER,
        )["type"]
        == "refresh"
    )


@pytest.mark.parametrize(
    "token_factory,path,payload",
    [
        (create_refresh_token, "/auth/me", None),
        (lambda user_id: create_access_token(user_id, "user"), "/auth/refresh", "body"),
    ],
)
def test_access_and_refresh_tokens_cannot_exchange_purpose(
    token_factory, path, payload
):
    token = token_factory(7)
    with patch.object(user_repo, "get_by_id", new_callable=AsyncMock) as get_user:
        if payload is None:
            response = _client().get(path, headers=_authorization(token))
        else:
            response = _client().post(path, json={"refresh_token": token})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert token not in response.text
    get_user.assert_not_awaited()


@pytest.mark.parametrize(
    "token,expected_code",
    [
        (_expired_token(), "token_expired"),
        ("not-a-jwt", "invalid_credentials"),
        (create_access_token(7, "user") + "modified", "invalid_credentials"),
    ],
)
def test_access_rejects_expired_invalid_and_modified_tokens(token, expected_code):
    with patch.object(user_repo, "get_by_id", new_callable=AsyncMock) as get_user:
        response = _client().get("/auth/me", headers=_authorization(token))
    assert response.status_code == 401
    assert response.json()["code"] == expected_code
    assert response.json()["message"]
    assert token not in response.text
    get_user.assert_not_awaited()


@pytest.mark.parametrize("database_user", [None, _user(active=False)])
def test_access_rejects_missing_and_inactive_database_user(database_user):
    token = create_access_token(7, "admin")
    with patch.object(
        user_repo, "get_by_id", new_callable=AsyncMock, return_value=database_user
    ):
        response = _client().get("/auth/me", headers=_authorization(token))
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert token not in response.text


@pytest.mark.parametrize(
    "token",
    [
        _expired_token(token_type="refresh"),
        "not-a-jwt",
        create_refresh_token(7) + "modified",
    ],
)
def test_refresh_rejects_expired_invalid_and_modified_tokens_without_lookup(token):
    with patch.object(user_repo, "get_by_id", new_callable=AsyncMock) as get_user:
        response = _client().post("/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert token not in response.text
    get_user.assert_not_awaited()


@pytest.mark.parametrize("database_user", [None, _user(active=False)])
def test_refresh_rejects_missing_and_inactive_database_user(database_user):
    token = create_refresh_token(7)
    with patch.object(
        user_repo, "get_by_id", new_callable=AsyncMock, return_value=database_user
    ):
        response = _client().post("/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert token not in response.text


def test_refresh_issues_valid_access_and_refresh_pair_for_active_user():
    refresh_token = create_refresh_token(7)
    with patch.object(
        user_repo, "get_by_id", new_callable=AsyncMock, return_value=_user()
    ):
        response = _client().post(
            "/auth/refresh", json={"refresh_token": refresh_token}
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"] != body["refresh_token"]
    access_payload = jwt.decode(
        body["access_token"],
        settings.JWT_SECRET,
        algorithms=[ALGORITHM],
        issuer=settings.JWT_ISSUER,
    )
    refresh_payload = jwt.decode(
        body["refresh_token"],
        settings.JWT_SECRET,
        algorithms=[ALGORITHM],
        issuer=settings.JWT_ISSUER,
    )
    assert (access_payload["sub"], access_payload["type"]) == ("7", "access")
    assert (refresh_payload["sub"], refresh_payload["type"]) == ("7", "refresh")


@pytest.mark.parametrize(
    "token_role,database_role,expected_status",
    [("admin", "user", 403), ("user", "admin", 200)],
)
def test_admin_authorization_uses_current_database_role(
    token_role, database_role, expected_status
):
    token = create_access_token(7, token_role)
    with (
        patch.object(
            user_repo,
            "get_by_id",
            new_callable=AsyncMock,
            return_value=_user(role=database_role),
        ),
        patch.object(
            admin_repo, "list_users", new_callable=AsyncMock, return_value=[]
        ) as list_users,
    ):
        response = _client().get("/admin/users", headers=_authorization(token))
    assert response.status_code == expected_status
    if expected_status == 403:
        assert response.json()["code"] == "forbidden"
        list_users.assert_not_awaited()
    else:
        assert response.json() == []
        list_users.assert_awaited_once()


@pytest.mark.parametrize(
    "method,path,json_body",
    [
        ("get", "/collections/8", None),
        ("post", "/collections/8/entries", {"printing_id": 13, "quantity": 1}),
        ("patch", "/collections/8/entries/13", {"quantity": 2}),
        ("delete", "/collections/8/entries/13", None),
    ],
)
def test_url_user_id_cannot_bypass_collection_ownership(method, path, json_body):
    token = create_access_token(7, "admin")
    with (
        patch.object(
            user_repo,
            "get_by_id",
            new_callable=AsyncMock,
            return_value=_user(role="admin"),
        ),
        patch.object(
            collection_repo, "list_for_user", new_callable=AsyncMock
        ) as list_entries,
        patch.object(
            collection_repo, "get_for_user_and_printing", new_callable=AsyncMock
        ) as get_entry,
        patch.object(
            collection_repo, "create_entry", new_callable=AsyncMock
        ) as create_entry,
        patch.object(
            collection_repo, "update_entry", new_callable=AsyncMock
        ) as update_entry,
        patch.object(
            collection_repo, "delete_entry", new_callable=AsyncMock
        ) as delete_entry,
    ):
        response = _client().request(
            method, path, headers=_authorization(token), json=json_body
        )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    list_entries.assert_not_awaited()
    get_entry.assert_not_awaited()
    create_entry.assert_not_awaited()
    update_entry.assert_not_awaited()
    delete_entry.assert_not_awaited()


def test_personal_filter_uses_jwt_identity_and_ignores_user_id_query():
    token = create_access_token(7, "user")
    with (
        patch.object(
            user_repo, "get_by_id", new_callable=AsyncMock, return_value=_user()
        ),
        patch.object(
            card_repo, "list_filtered", new_callable=AsyncMock, return_value=([], 0)
        ) as filtered,
    ):
        response = _client().get(
            "/cards?collection_status=owned&user_id=8",
            headers=_authorization(token),
        )
    assert response.status_code == 200, response.text
    filters = filtered.await_args.kwargs["filters"]
    assert filters.collection_statuses == ("owned",)
    assert filters.collection_user_id == 7


def test_public_filters_do_not_validate_an_unrelated_bad_bearer():
    with (
        patch.object(user_repo, "get_by_id", new_callable=AsyncMock) as get_user,
        patch.object(
            card_repo, "list_paginated", new_callable=AsyncMock, return_value=([], 0)
        ) as list_cards,
    ):
        response = _client().get(
            "/cards?limit=1", headers=_authorization("expired-or-invalid")
        )
    assert response.status_code == 200
    get_user.assert_not_awaited()
    list_cards.assert_awaited_once()
