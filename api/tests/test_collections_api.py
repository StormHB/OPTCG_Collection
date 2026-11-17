"""API testovi autorizacije. Repository i DB zamijenjeni su testnim objektima."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import create_app
from app.repositories import card_loan_repo, collection_repo


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
        assert repo.await_args.kwargs == {"limit": 50, "offset": 0}


def test_stranicenje_kolekcije_prosljeduje_limit_i_offset():
    client = _create_test_client(user_id=7)
    with patch.object(collection_repo, "list_for_user", new_callable=AsyncMock) as repo:
        repo.return_value = []
        response = client.get("/collections/7?limit=20&offset=20")
        assert response.status_code == 200
        assert response.json() == []
        assert repo.await_args.kwargs == {"limit": 20, "offset": 20}


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "offset=-1", "offset=2147483648"]
)
@pytest.mark.parametrize(
    "path,repo_module,repo_method",
    [
        ("/collections/7", collection_repo, "list_for_user"),
        ("/collections/7/loans", card_loan_repo, "list_for_owner"),
    ],
)
def test_nevaljano_stranicenje_je_odbijeno_prije_upita(
    query, path, repo_module, repo_method
):
    client = _create_test_client(user_id=7)
    with patch.object(repo_module, repo_method, new_callable=AsyncMock) as repo:
        response = client.get(f"{path}?{query}")
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"
        repo.assert_not_awaited()


def test_tudja_kolekcija_je_zabranjena_prije_upita():
    client = _create_test_client(user_id=7)
    with patch.object(collection_repo, "list_for_user", new_callable=AsyncMock) as repo:
        response = client.get("/collections/8?limit=1&offset=1")
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
