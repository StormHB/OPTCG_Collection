"""Korak 10B: API, privatnost, OR statusi i SQL nad stvarnim tablicama."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.optional_auth import get_collection_filter_user
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.models import Base
from app.models.card import Card
from app.models.card_metadata import Color
from app.models.card_printing import CardPrinting
from app.models.card_set import CardSet
from app.models.collection_entry import CollectionEntry
from app.models.user import User
from app.repositories import card_repo
from app.routers.cards import router as cards_router
from app.schemas.card_search import CardSearchFilters
from app.services import card_service


class AsyncDbBridge:
    def __init__(self, session):
        self.session = session

    async def scalar(self, statement):
        return self.session.scalar(statement)

    async def scalars(self, statement):
        return self.session.scalars(statement)


@pytest.fixture()
def seeded_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        op01 = CardSet(id=1, code="OP01", name="OP01", sort_order=1)
        op02 = CardSet(id=2, code="OP02", name="OP02", sort_order=2)
        prb = CardSet(id=3, code="PRB01", name="PRB", sort_order=3)
        don = CardSet(id=4, code="DON", name="DON", sort_order=4)
        red = Color(name="Red")
        blue = Color(name="Blue")
        session.add_all([op01, op02, prb, don, red, blue])
        session.add_all(
            [
                User(id=7, username="seven", password_hash="test", role="user"),
                User(id=8, username="eight", password_hash="test", role="admin"),
            ]
        )

        def card(id_, code, name, base_set, kind=None, color=None):
            return Card(
                id=id_, code=code, name=name, original_set=base_set,
                card_type=kind, colors=[color] if color else [],
            )

        def printing(card_, product_set, variant="regular", rarity="R"):
            p = CardPrinting(
                card=card_, product_set=product_set,
                variant_code=variant, rarity=rarity,
            )
            session.add(p)
            session.flush()
            return p

        def owned(p, qty, user=7):
            session.add(CollectionEntry(user_id=user, printing_id=p.id, quantity=qty))

        a = card(1, "OP01-001", "Red A", op01, "Character", red)
        owned(printing(a, op01), 4)
        owned(printing(a, op01, "alt", "SR"), 1)
        owned(printing(a, prb), 0)

        b = card(2, "OP02-001", "Leader B", op02, None, red)
        owned(printing(b, op02, rarity="L"), 1)

        c = card(3, "DON-001", "Don C", don)
        owned(printing(c, don, rarity="DON!!"), 9)

        d = card(4, "OP01-003", "Missing D", op01, "Character", blue)
        owned(printing(d, op01), 4, user=8)  # tuđi primjerci nisu naši

        e = card(5, "OP02-002", "Not Full E", op02, "Character", blue)
        owned(printing(e, op02), 2)

        f = card(6, "OP01-004", "PRB Only F", op01, "Character", red)
        owned(printing(f, op01), 0)
        owned(printing(f, prb), 4)

        g = card(7, "OP02-003", "Split G", op02, "Character", blue)
        owned(printing(g, op02), 2)
        owned(printing(g, op02, "alt", "SR"), 2)

        h = card(8, "DON-002", "Don H", don, "DON!!")
        owned(printing(h, don, rarity="DON!!"), 10)

        i = card(9, "OP02-004", "Leader I", op02, "Leader")
        owned(printing(i, op02, rarity="L"), 4)

        j = card(10, "OP01-005", "Zero J", op01, "Character")
        owned(printing(j, op01), 0)

        session.commit()
        yield AsyncDbBridge(session)
    engine.dispose()


def do_search(db, *, user_id=7, statuses=("owned",), **other):
    filters = CardSearchFilters(
        collection_statuses=statuses,
        collection_user_id=user_id,
        **other,
    )
    items, total = asyncio.run(
        card_repo.list_filtered(db, limit=100, offset=0, filters=filters)
    )
    return [c.code for c in items], total


def make_client(db, user_id=7):
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(cards_router, prefix="/cards")

    async def fake_db():
        yield db

    app.dependency_overrides[get_db] = fake_db
    if user_id is not None:
        async def fake_user():
            return SimpleNamespace(id=user_id, role="user", is_active=True)
        app.dependency_overrides[get_collection_filter_user] = fake_user
    return TestClient(app)


def test_owned_positive_quantity_only_and_other_user_hidden(seeded_db):
    codes, total = do_search(seeded_db)
    assert codes == [
        "DON-001", "DON-002", "OP01-001", "OP01-004",
        "OP02-001", "OP02-002", "OP02-003", "OP02-004",
    ]
    assert total == 8
    assert "OP01-003" not in codes  # postoji samo kod usera 8


def test_missing_means_no_positive_owned_printing(seeded_db):
    assert do_search(seeded_db, statuses=("missing",)) == (
        ["OP01-003", "OP01-005"], 2
    )
    assert do_search(seeded_db, user_id=8, statuses=("missing",))[1] == 9


def test_playset_matches_10a_rules_including_leader_rarity_and_don(seeded_db):
    assert do_search(seeded_db, statuses=("playset",)) == (
        ["DON-002", "OP01-001", "OP01-004", "OP02-001", "OP02-004"], 5
    )
    # 9 DON! nema playset, 2 + 2 različitih ilustracija ne zbraja se.
    assert "DON-001" not in do_search(seeded_db, statuses=("playset",))[0]
    assert "OP02-003" not in do_search(seeded_db, statuses=("playset",))[0]


def test_printing_filters_use_same_printing_as_personal_status(seeded_db):
    assert do_search(seeded_db, statuses=("owned",), sets=("PRB01",)) == (
        ["OP01-004"], 1
    )
    assert do_search(seeded_db, statuses=("missing",), sets=("OP01",)) == (
        ["OP01-003", "OP01-004", "OP01-005"], 3
    )
    assert do_search(seeded_db, statuses=("playset",), sets=("OP01",)) == (
        ["OP01-001"], 1
    )
    assert do_search(seeded_db, statuses=("playset",), sets=("PRB01",)) == (
        ["OP01-004"], 1
    )
    assert do_search(seeded_db, statuses=("playset",), rarities=("SR",)) == ([], 0)
    assert do_search(seeded_db, statuses=("playset",), rarities=("R",)) == (
        ["OP01-001", "OP01-004"], 2
    )
    assert do_search(
        seeded_db, statuses=("playset",), sets=("PRB01",), variants=("alt",)
    ) == ([], 0)


def test_status_or_between_values_and_and_with_other_filters(seeded_db):
    assert do_search(seeded_db, statuses=("owned", "missing"))[1] == 10
    assert do_search(seeded_db, statuses=("playset", "missing")) == (
        [
            "DON-002", "OP01-001", "OP01-003", "OP01-004",
            "OP01-005", "OP02-001", "OP02-004",
        ],
        7,
    )
    assert do_search(seeded_db, statuses=("owned", "playset"))[1] == 8
    assert do_search(seeded_db, statuses=("playset",), colors=("Red",)) == (
        ["OP01-001", "OP01-004", "OP02-001"], 3
    )
    assert do_search(
        seeded_db, statuses=("missing",), colors=("Blue",), sets=("OP01",)
    ) == (
        ["OP01-003"], 1
    )


def test_pagination_after_personal_filter_no_duplicates(seeded_db):
    filters = CardSearchFilters(collection_statuses=("owned",), collection_user_id=7)
    items, total = asyncio.run(
        card_repo.list_filtered(seeded_db, limit=2, offset=2, filters=filters)
    )
    assert [card.code for card in items] == ["OP01-001", "OP01-004"]
    assert total == 8


def test_api_public_unchanged_without_filter(seeded_db):
    res = make_client(seeded_db, user_id=None).get("/cards?limit=3")
    assert res.status_code == 200, res.text
    assert res.json()["total"] == 10


def test_api_public_with_stale_bearer_still_works(seeded_db):
    res = make_client(seeded_db, user_id=None).get(
        "/cards?limit=3", headers={"Authorization": "Bearer expired-or-invalid"}
    )
    assert res.status_code == 200
    assert res.json()["total"] == 10


def test_api_requires_token_before_private_repo_query(seeded_db):
    with patch.object(card_repo, "list_filtered", new_callable=AsyncMock) as repo:
        res = make_client(seeded_db, user_id=None).get("/cards?collection_status=owned")
        assert res.status_code == 401
        assert res.json()["code"] == "invalid_credentials"
        repo.assert_not_awaited()


def test_api_invalid_jwt_still_fails_without_looking_up_collection(seeded_db):
    with patch.object(card_repo, "list_filtered", new_callable=AsyncMock) as repo:
        res = make_client(seeded_db, user_id=None).get(
            "/cards?collection_status=missing",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert res.status_code == 401
        repo.assert_not_awaited()


@pytest.mark.parametrize("status", ["mine", "none", "PLAYSET", "", "owned,missing"])
def test_api_invalid_personal_status_422(seeded_db, status):
    res = make_client(seeded_db).get("/cards", params={"collection_status": status})
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "validation_error"


def test_api_jwt_user_scope_and_repeated_status_or(seeded_db):
    res = make_client(seeded_db, user_id=7).get(
        "/cards?collection_status=missing&collection_status=playset"
        "&colors=Red&colors=Blue"
    )
    assert res.status_code == 200, res.text
    assert [card["code"] for card in res.json()["items"]] == (
        ["OP01-001", "OP01-003", "OP01-004", "OP02-001"]
    )
    assert res.json()["total"] == 4


def test_private_status_user_id_is_not_user_controlled(seeded_db):
    res = make_client(seeded_db, user_id=7).get(
        "/cards?collection_status=missing&user_id=8"
    )
    assert res.status_code == 200
    assert [item["code"] for item in res.json()["items"]] == ["OP01-003", "OP01-005"]


def test_filter_does_not_change_collection_or_loans(seeded_db):
    before = list(
        seeded_db.session.query(CollectionEntry.id, CollectionEntry.quantity)
        .order_by(CollectionEntry.id)
    )
    make_client(seeded_db).get("/cards?collection_status=playset")
    after = list(
        seeded_db.session.query(CollectionEntry.id, CollectionEntry.quantity)
        .order_by(CollectionEntry.id)
    )
    assert before == after


def test_service_rejects_filter_without_authenticated_identity(seeded_db):
    with pytest.raises(AppError) as ex:
        asyncio.run(
            card_service.get_cards(
                seeded_db, limit=20, offset=0,
                filters=CardSearchFilters(collection_statuses=("owned",)),
            )
        )
    assert ex.value.status_code == 401
    assert ex.value.code == "invalid_credentials"


# Korak 10B: ulazne oznake seta mogu imati crticu, dok baza čuva OP01.
@pytest.mark.parametrize("alias", ["OP01", "op01", "OP-01", "op-01", " Op-01 "])
def test_set_code_alias_owned_same_as_canonical(seeded_db, alias):
    assert do_search(seeded_db, sets=(alias,)) == do_search(
        seeded_db, sets=("OP01",)
    )


def test_set_alias_respects_same_printing_and_missing(seeded_db):
    assert do_search(seeded_db, statuses=("owned",), sets=("op-01",)) == (
        ["OP01-001"], 1
    )
    assert do_search(seeded_db, statuses=("missing",), sets=("OP-01",)) == (
        ["OP01-003", "OP01-004", "OP01-005"], 3
    )


def test_public_api_set_alias_and_search_alias(seeded_db):
    client = make_client(seeded_db, user_id=None)
    canonical = client.get("/cards", params={"sets": "OP01"})
    assert canonical.status_code == 200
    for alias in ("OP-01", "op-01", " OP-01 "):
        r = client.get("/cards", params={"sets": alias})
        assert r.status_code == 200, r.text
        assert r.json() == canonical.json()

    expected = client.get("/cards", params={"search": "OP01"})
    assert expected.status_code == 200
    for query in ("OP-01", "op-01", "op01"):
        r = client.get("/cards", params={"search": query})
        assert r.status_code == 200, r.text
        assert r.json() == expected.json()


def test_set_alias_preserves_other_prefixes(seeded_db):
    from app.repositories.card_repo import _normalized_set_values

    assert _normalized_set_values(
        ("OP-01", "op01", "PRB-01", "EB-03", "ST-01", "DON", "P-001")
    ) == ("op01", "prb01", "eb03", "st01", "don", "p-001")
