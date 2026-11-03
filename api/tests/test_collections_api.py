"""API testovi autorizacije. Repository i DB zamijenjeni su testnim objektima."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import create_app
from app.repositories import collection_repo


def _create_test_client(user_id: int | None):
    app = create_app()

    async def fake_get_db():
        yield object()  # Repo je mockan; u testu ne treba stvarna baza.

    app.dependency_overrides[get_db] = fake_get_db
    if user_id is not None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=user_id, role="user", is_active=True
        )
    return TestClient(app)


def test_vlasnik_dobiva_svoje_zapise():
    client = _create_test_client(user_id=7)
    fake_entry = SimpleNamespace(id=21, printing_id=11, quantity=4, note="Trade")
    with patch.object(collection_repo, "list_for_user", new_callable=AsyncMock) as repo:
        repo.return_value = [fake_entry]
        response = client.get("/collections/7")
        assert response.status_code == 200
        assert response.json() == [
            {"id": 21, "printing_id": 11, "quantity": 4, "note": "Trade"}
        ]
        repo.assert_awaited_once()
        assert repo.await_args.args[1] == 7


def test_tudja_kolekcija_je_zabranjena_prije_upita():
    client = _create_test_client(user_id=7)
    with patch.object(collection_repo, "list_for_user", new_callable=AsyncMock) as repo:
        response = client.get("/collections/8")
        assert response.status_code == 403
        assert response.json()["code"] == "forbidden"
        repo.assert_not_awaited()


def test_neprijavljeni_korisnik_dobiva_401():
    client = _create_test_client(user_id=None)
    with patch.object(collection_repo, "list_for_user", new_callable=AsyncMock) as repo:
        response = client.get("/collections/7")
        assert response.status_code == 401
        repo.assert_not_awaited()


def test_prazna_kolekcija_vraca_prazan_popis():
    client = _create_test_client(user_id=7)
    with patch.object(collection_repo, "list_for_user", new_callable=AsyncMock) as repo:
        repo.return_value = []
        response = client.get("/collections/7")
        assert response.status_code == 200
        assert response.json() == []
