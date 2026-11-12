"""Testovi GET /cards, bez povezivanja na PostgreSQL."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.main import create_app
from app.repositories import card_repo


def _make_client() -> TestClient:
    app = create_app()

    async def fake_get_db():
        yield object()  # Repository mockan; stvarna baza nije potrebna.

    app.dependency_overrides[get_db] = fake_get_db
    return TestClient(app)


def test_prazan_katalog_vraca_praznu_stranicu():
    client = _make_client()
    with patch.object(card_repo, "list_paginated", new_callable=AsyncMock) as repo:
        repo.return_value = ([], 0)
        response = client.get("/cards")
        assert response.status_code == 200
        assert response.json() == {
            "items": [], "total": 0, "limit": 20, "offset": 0
        }
        repo.assert_awaited_once()
        assert repo.await_args.kwargs == {"limit": 20, "offset": 0}


def test_katalog_vraca_kartu_i_ukupan_broj():
    client = _make_client()
    card = SimpleNamespace(
        id=7,
        code="OP01-001",
        name="Roronoa Zoro",
        original_set_id=1,
        card_type="Leader",
        cost=None,
        power=5000,
        counter=None,
        life=5,
    )
    with patch.object(card_repo, "list_paginated", new_callable=AsyncMock) as repo:
        repo.return_value = ([card], 123)
        response = client.get("/cards?limit=2&offset=4")
        assert response.status_code == 200
        assert response.json() == {
            "items": [{
                "id": 7,
                "code": "OP01-001",
                "name": "Roronoa Zoro",
                "original_set_id": 1,
                "card_type": "Leader",
                "cost": None,
                "power": 5000,
                "counter": None,
                "life": 5,
            }],
            "total": 123,
            "limit": 2,
            "offset": 4,
        }
        repo.assert_awaited_once()
        assert repo.await_args.kwargs == {"limit": 2, "offset": 4}


@pytest.mark.parametrize(
    "params", ["limit=0", "limit=101", "offset=-1", "limit=abc"]
)
def test_neispravna_paginacija_vraca_422(params: str):
    client = _make_client()
    with patch.object(card_repo, "list_paginated", new_callable=AsyncMock) as repo:
        response = client.get(f"/cards?{params}")
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"
        repo.assert_not_awaited()
