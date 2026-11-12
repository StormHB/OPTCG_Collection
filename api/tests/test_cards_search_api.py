"""Kombinacija API validacije i SQL testova nad privremenom SQLite bazom.

Nema potrebe za Dockerom, stvarnim PostgreSQL-om niti korisničkim podacima.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.main import create_app
from app.models import Base
from app.models.card import Card
from app.models.card_metadata import Archetype, Attribute, Color, Keyword
from app.models.card_printing import CardPrinting
from app.models.card_set import CardSet
from app.repositories import card_repo
from app.schemas.card_search import CardSearchFilters


class AsyncDbBridge:
    """Dopušta testirati prave SQL izraze koristeći sinkroni SQLite Session."""

    def __init__(self, session: Session):
        self.session = session

    async def scalar(self, statement):
        return self.session.scalar(statement)

    async def scalars(self, statement):
        return self.session.scalars(statement)


def _card(id_, code, name, set_, card_type, cost, power, counter, **relations):
    return Card(
        id=id_,
        code=code,
        name=name,
        original_set=set_,
        card_type=card_type,
        cost=cost,
        power=power,
        counter=counter,
        **relations,
    )


@pytest.fixture()
def catalog_db():
    """Namjerno složeni podaci: dual-color, M:N i više izdanja iste karte."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        op01 = CardSet(id=1, code="OP01", name="Set 1", sort_order=1)
        op02 = CardSet(id=2, code="OP02", name="Set 2", sort_order=2)
        prb01 = CardSet(id=3, code="PRB01", name="Reprint", sort_order=3)
        don = CardSet(id=4, code="DON", name="DON!!", sort_order=4)
        red, yellow, green = [Color(name=n) for n in ("Red", "Yellow", "Green")]
        slash, strike = [Attribute(name=n) for n in ("Slash", "Strike")]
        straw, wb = [
            Archetype(name=n) for n in ("Straw Hat Crew", "Whitebeard Pirates")
        ]
        rush, blocker = [Keyword(name=n) for n in ("Rush", "Blocker")]

        c1 = _card(
            1, "OP01-001", "Dual Color", op01, "Character", 1, 6000, 1000,
            colors=[red, green], attributes=[slash, strike],
            archetypes=[straw, wb], keywords=[rush],
        )
        c2 = _card(
            2, "OP01-002", "Yellow Warrior", op01, "Character", 2, 6000, 2000,
            colors=[yellow], attributes=[strike], archetypes=[wb], keywords=[blocker],
        )
        c3 = _card(
            3, "OP02-003", "Red Leader", op02, "Leader", 3, 5000, None,
            colors=[red], attributes=[slash], archetypes=[straw],
        )
        c4 = _card(
            4, "OP02-004", "Green Soul", op02, "Character", 2, 6000, 0,
            colors=[green], attributes=[strike], archetypes=[straw],
        )
        c5 = _card(5, "DON-001", "DON!!", don, "DON!!", None, None, None)
        c6 = _card(6, "OP02-005", "A_100% Card", op02, "Event", 1, 0, None)

        def printing(card, product_set, variant, rarity, block=None):
            return CardPrinting(
                card=card,
                product_set=product_set,
                variant_code=variant,
                rarity=rarity,
                block_icon=block,
            )

        session.add_all(
            [
                printing(c1, op01, "regular", "R", "1"),
                printing(c1, prb01, "regular", "R", "2"),
                printing(c1, op01, "manga", "SR", "3"),
                printing(c2, op01, "regular", "SR", "1"),
                printing(c3, op02, "regular", "L", "2"),
                printing(c4, op02, "regular", "SR", "3"),
                printing(c5, don, "regular", "DON!!"),
                printing(c6, op02, "regular", "C"),
            ]
        )
        session.commit()
        yield AsyncDbBridge(session)
    engine.dispose()


def _search(db, *, limit=20, offset=0, **kwargs):
    filters = CardSearchFilters(**kwargs)
    cards, total = asyncio.run(
        card_repo.list_filtered(db, limit=limit, offset=offset, filters=filters)
    )
    return [c.code for c in cards], total


def _test_client():
    app = create_app()

    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    return TestClient(app)


def test_api_repeated_values_are_parsed_as_or():
    with patch.object(card_repo, "list_filtered", new_callable=AsyncMock) as repo:
        repo.return_value = ([], 0)
        res = _test_client().get(
            "/cards?colors=Red&colors=Yellow&costs=1&costs=2&powers=6000"
        )
        assert res.status_code == 200, res.text
        filters = repo.await_args.kwargs["filters"]
        assert filters.colors == ("Red", "Yellow")
        assert filters.costs == (1, 2)
        assert filters.powers == (6000,)


def test_api_no_filters_keeps_old_repository():
    with patch.object(card_repo, "list_paginated", new_callable=AsyncMock) as repo:
        repo.return_value = ([], 0)
        res = _test_client().get("/cards?limit=5&offset=2")
        assert res.status_code == 200
        repo.assert_awaited_once()
        assert repo.await_args.kwargs == {"limit": 5, "offset": 2}


@pytest.mark.parametrize(
    "q",
    [
        "counter_values=abc",
        "counter_values=-1",
        "counter_values=1.5",
        "costs=-2",
        "powers=abc",
    ],
)
def test_api_invalid_filters_return_422(q):
    res = _test_client().get(f"/cards?{q}")
    assert res.status_code == 422, res.text


def test_or_within_colors_and_costs_and_between_categories(catalog_db):
    codes, total = _search(
        catalog_db, colors=("Red", "Yellow"), costs=(1, 2), powers=(6000,)
    )
    assert codes == ["OP01-001", "OP01-002"]
    assert total == 2


def test_multivalued_attributes_and_archetypes_no_duplicates(catalog_db):
    codes, total = _search(
        catalog_db,
        attributes=("Slash", "Strike"),
        archetypes=("Whitebeard Pirates", "Straw Hat Crew"),
        colors=("Red", "Green"),
    )
    assert codes == ["OP01-001", "OP02-003", "OP02-004"]
    assert total == 3


def test_keywords_or_and_color_and_type(catalog_db):
    codes, total = _search(
        catalog_db,
        keywords=("Rush", "Blocker"), colors=("Red",), card_types=("Character",)
    )
    assert codes == ["OP01-001"]
    assert total == 1


def test_counter_none_is_distinct_from_zero(catalog_db):
    codes_none, total_none = _search(catalog_db, counter_values=("none",))
    codes_zero, total_zero = _search(catalog_db, counter_values=("0",))
    codes_both, total_both = _search(catalog_db, counter_values=("none", "0"))
    assert codes_none == ["DON-001", "OP02-003", "OP02-005"]
    assert total_none == 3
    assert codes_zero == ["OP02-004"]
    assert total_zero == 1
    assert codes_both == ["DON-001", "OP02-003", "OP02-004", "OP02-005"]
    assert total_both == 4


def test_set_filter_uses_product_set_for_reprints(catalog_db):
    assert _search(catalog_db, sets=("PRB01",)) == (["OP01-001"], 1)
    assert _search(catalog_db, sets=("DON",)) == (["DON-001"], 1)


def test_printing_filters_must_match_same_printing(catalog_db):
    # Karta ima PRB01-regular i OP01-manga: NE postoji PRB01-manga.
    assert _search(catalog_db, sets=("PRB01",), variants=("manga",)) == ([], 0)
    assert _search(
        catalog_db,
        sets=("OP01",),
        variants=("manga",),
        rarities=("SR",),
        block_icons=("3",),
    ) == (["OP01-001"], 1)
    assert _search(catalog_db, sets=("PRB01",), rarities=("SR",)) == ([], 0)


def test_rarity_and_variant_combination_does_not_mix_printings(catalog_db):
    assert _search(catalog_db, rarities=("SR",), variants=("regular",)) == (
        ["OP01-002", "OP02-004"], 2
    )
    assert _search(catalog_db, rarities=("SR",), variants=("manga",)) == (
        ["OP01-001"], 1
    )


def test_pagination_applies_after_filtering(catalog_db):
    assert _search(catalog_db, colors=("Red",), limit=1, offset=1) == (
        ["OP02-003"], 2
    )


def test_search_case_insensitive_and_literal_wildcards(catalog_db):
    assert _search(catalog_db, search="red leader") == (["OP02-003"], 1)
    assert _search(catalog_db, search="OP01-00") == (["OP01-001", "OP01-002"], 2)
    assert _search(catalog_db, search="100%") == (["OP02-005"], 1)
    assert _search(catalog_db, search="_") == (["OP02-005"], 1)


def test_unknown_values_return_no_cards(catalog_db):
    assert _search(catalog_db, colors=("Pink",)) == ([], 0)
