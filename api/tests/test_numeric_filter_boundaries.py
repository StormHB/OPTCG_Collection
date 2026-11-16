"""Korak 11A.1: stroge numericke granice za GET /cards."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.main import create_app
from app.repositories import card_repo


def client():
    app = create_app()

    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    return TestClient(app)


@pytest.mark.parametrize(
    "query",
    [
        "costs=-1",
        "costs=11",
        "costs=1.5",
        "costs=abc",
        "powers=-1",
        "powers=13001",
        "powers=6000.5",
        "powers=abc",
        "counter_values=-1",
        "counter_values=1.5",
        "counter_values=abc",
        "counter_values=none",
        "counter_values=3000",
        "counter_values=2147483648",
        "counter_values=" + "9" * 4400,
        "counter_missing=unknown",
    ],
)
def test_invalid_numeric_filters_return_422_without_repository_call(query):
    with patch.object(card_repo, "list_filtered", new_callable=AsyncMock) as repo:
        response = client().get("/cards?" + query)
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "validation_error"
        assert response.json()["errors"]
        repo.assert_not_awaited()


@pytest.mark.parametrize(
    "query,field,expected",
    [
        ("costs=0", "costs", (0,)),
        ("costs=10", "costs", (10,)),
        ("powers=0", "powers", (0,)),
        ("powers=13000", "powers", (13000,)),
        ("counter_values=0", "counter_values", ("0",)),
        ("counter_values=1000", "counter_values", ("1000",)),
        ("counter_values=2000", "counter_values", ("2000",)),
        ("counter_missing=true", "counter_values", ("none",)),
        (
            "counter_values=0&counter_missing=true",
            "counter_values",
            ("0", "none"),
        ),
    ],
)
def test_valid_boundaries_keep_filter_values(query, field, expected):
    with patch.object(card_repo, "list_filtered", new_callable=AsyncMock) as repo:
        repo.return_value = ([], 0)
        response = client().get("/cards?" + query)
        assert response.status_code == 200, response.text
        filters = repo.await_args.kwargs["filters"]
        assert getattr(filters, field) == expected


def test_repeated_numeric_values_still_use_or():
    with patch.object(card_repo, "list_filtered", new_callable=AsyncMock) as repo:
        repo.return_value = ([], 0)
        response = client().get("/cards?costs=0&costs=10&powers=6000")
        assert response.status_code == 200, response.text
        filters = repo.await_args.kwargs["filters"]
        assert filters.costs == (0, 10)
        assert filters.powers == (6000,)
