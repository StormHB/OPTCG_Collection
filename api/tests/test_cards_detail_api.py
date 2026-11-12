"""Testovi javnih detalja karata, uz mockan repository umjesto PostgreSQL-a."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.main import create_app
from app.repositories import card_repo


def _make_client() -> TestClient:
    app = create_app()

    async def fake_get_db():
        yield object()

    app.dependency_overrides[get_db] = fake_get_db
    return TestClient(app)


def _make_card():
    return SimpleNamespace(
        id=12,
        code="OP01-001",
        name="Roronoa Zoro",
        original_set_id=1,
        card_type="Leader",
        cost=None,
        power=5000,
        counter=None,
        life=5,
        color="Red/Green",
        attribute="Slash",
        affiliation_text="Straw Hat Crew",
        effect_text="Example effect",
        colors=[SimpleNamespace(name="Red"), SimpleNamespace(name="Green")],
        attributes=[SimpleNamespace(name="Slash")],
        archetypes=[SimpleNamespace(name="Straw Hat Crew")],
        keywords=[SimpleNamespace(name="When Attacking")],
        printings=[
            SimpleNamespace(
                id=40, product_set_id=1, variant_code="regular", rarity="L",
                image_url="https://example.com/card40.png", block_icon="1"
            ),
            SimpleNamespace(
                id=41, product_set_id=1, variant_code="alt", rarity="L",
                image_url=None, block_icon="1"
            ),
        ],
    )


def test_card_detail_includes_printings_and_metadata():
    client = _make_client()
    with patch.object(card_repo, "get_by_id_with_details", new_callable=AsyncMock) as repo:
        repo.return_value = _make_card()
        response = client.get("/cards/12")  # Javni endpoint, bez tokena.
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["code"] == "OP01-001"
        assert body["colors"] == ["Green", "Red"]
        assert body["attributes"] == ["Slash"]
        assert body["archetypes"] == ["Straw Hat Crew"]
        assert body["keywords"] == ["When Attacking"]
        assert [p["variant_code"] for p in body["printings"]] == ["alt", "regular"]
        assert body["printings"][0]["image_url"] is None
        assert "password_hash" not in response.text
        repo.assert_awaited_once()
        assert repo.await_args.args[1] == 12


def test_card_detail_without_printings():
    client = _make_client()
    card = _make_card()
    card.printings = []
    with patch.object(card_repo, "get_by_id_with_details", new_callable=AsyncMock) as repo:
        repo.return_value = card
        response = client.get("/cards/12")
        assert response.status_code == 200
        assert response.json()["printings"] == []


def test_card_not_found_returns_404():
    client = _make_client()
    with patch.object(card_repo, "get_by_id_with_details", new_callable=AsyncMock) as repo:
        repo.return_value = None
        response = client.get("/cards/999999")
        assert response.status_code == 404
        assert response.json() == {
            "code": "not_found", "message": "Karta nije pronadena"
        }


def test_invalid_card_ids_return_422():
    client = _make_client()
    with patch.object(card_repo, "get_by_id_with_details", new_callable=AsyncMock) as repo:
        for path in ("/cards/0", "/cards/-1", "/cards/xyz"):
            response = client.get(path)
            assert response.status_code == 422
            assert response.json()["code"] == "validation_error"
        repo.assert_not_awaited()
