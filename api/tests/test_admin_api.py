"""Autorizacija GET /admin/users bez spajanja na stvarni PostgreSQL."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import create_app
from app.repositories import admin_repo


def _make_client(role: str | None) -> TestClient:
    app = create_app()

    async def fake_db():
        yield object()  # Repository je mockan.

    app.dependency_overrides[get_db] = fake_db
    if role is not None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=1, role=role, is_active=True
        )
    return TestClient(app)


def test_admin_moze_vidjeti_korisnike():
    client = _make_client("admin")
    admin = SimpleNamespace(
        id=1, username="admin_test", role="admin",
        is_active=True, password_hash="ne_smije_izaci",
    )
    with patch.object(admin_repo, "list_users", new_callable=AsyncMock) as repo:
        repo.return_value = [admin]
        response = client.get("/admin/users?limit=10&offset=0")
        assert response.status_code == 200
        assert response.json() == [
            {"id": 1, "username": "admin_test", "role": "admin", "is_active": True}
        ]
        assert "password_hash" not in response.text
        repo.assert_awaited_once()
        assert repo.await_args.kwargs == {"limit": 10, "offset": 0}


def test_obicni_korisnik_dobiva_403():
    client = _make_client("user")
    with patch.object(admin_repo, "list_users", new_callable=AsyncMock) as repo:
        response = client.get("/admin/users")
        assert response.status_code == 403
        assert response.json()["code"] == "forbidden"
        repo.assert_not_awaited()


def test_bez_tokena_dobiva_401():
    client = _make_client(None)
    with patch.object(admin_repo, "list_users", new_callable=AsyncMock) as repo:
        response = client.get("/admin/users")
        assert response.status_code == 401
        repo.assert_not_awaited()


def test_limit_izvan_raspona_dobiva_422():
    client = _make_client("admin")
    with patch.object(admin_repo, "list_users", new_callable=AsyncMock) as repo:
        response = client.get("/admin/users?limit=101")
        assert response.status_code == 422
        repo.assert_not_awaited()
