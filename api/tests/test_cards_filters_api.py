"""Testovi GET /cards/filters bez stvarne PostgreSQL baze."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.main import create_app
from app.repositories import card_repo


def _client():
    app = create_app()

    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    return TestClient(app)


def _values():
    return {
        "sets": [
            SimpleNamespace(id=1, code="OP01", name="OP01"),
            SimpleNamespace(id=64, code="DON", name="DON!! Cards"),
        ],
        "colors": ["Yellow", "Red", "Green"],
        "attributes": ["Slash", "?"],
        "keywords": ["Rush", "Blocker", "Rush"],
        "archetypes": ["Straw Hat Crew", "Whitebeard Pirates"],
        "card_types": ["Leader", "Character"],
        "costs": [2, 1, 2],
        "powers": [6000, 5000, 6000],
        "counter_values": [1000, 2000],
        "block_icons": ["2", "5"],
        "rarities": ["SR", "XX"],
        "variants": ["alt-1", "regular"],
    }


def test_filters_are_public_and_route_is_not_treated_as_card_id():
    with patch.object(card_repo, "get_filter_values", new_callable=AsyncMock) as repo:
        repo.return_value = _values()
        response = _client().get("/cards/filters")
        assert response.status_code == 200, response.text
        repo.assert_awaited_once()


def test_filters_sort_deduplicate_and_include_new_values():
    with patch.object(card_repo, "get_filter_values", new_callable=AsyncMock) as repo:
        repo.return_value = _values()
        response = _client().get("/cards/filters")
        data = response.json()
        assert data["colors"] == ["Red", "Green", "Yellow"]
        assert data["attributes"] == ["Slash", "?"]
        assert data["keywords"] == ["Blocker", "Rush"]
        assert data["costs"] == [1, 2]
        assert data["powers"] == [5000, 6000]
        assert "DON!!" in data["card_types"]
        assert data["rarities"][-1] == "XX"
        assert data["variants"] == ["regular", "alt-1"]


def test_counter_null_is_distinct_from_numerical_zero():
    with patch.object(card_repo, "get_filter_values", new_callable=AsyncMock) as repo:
        values = _values()
        values["counter_values"] = [0, 2000]
        repo.return_value = values
        data = _client().get("/cards/filters").json()
        assert data["counter_values"] == [None, 0, 1000, 2000]


def test_sets_and_archetypes_are_loaded_from_database():
    with patch.object(card_repo, "get_filter_values", new_callable=AsyncMock) as repo:
        values = _values()
        values["archetypes"] = []
        repo.return_value = values
        data = _client().get("/cards/filters").json()
        assert data["archetypes"] == []
        assert data["sets"] == [
            {"id": 1, "code": "OP01", "name": "OP01"},
            {"id": 64, "code": "DON", "name": "DON!! Cards"},
        ]


def test_empty_catalog_still_has_stable_categories():
    with patch.object(card_repo, "get_filter_values", new_callable=AsyncMock) as repo:
        values = _values()
        for field in ("costs", "powers", "card_types", "rarities", "variants", "block_icons"):
            values[field] = []
        repo.return_value = values
        data = _client().get("/cards/filters").json()
        assert data["costs"] == []
        assert data["powers"] == []
        assert data["card_types"] == ["Leader", "Character", "Event", "Stage", "DON!!"]
        assert data["variants"] == ["regular"]
        assert data["block_icons"] == ["1", "2", "3", "4", "5", "X"]
