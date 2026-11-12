"""Case-insensitive catalog filter regression tests (no running PostgreSQL needed)."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.main import create_app
from app.core.deps import get_db
from app.models import Base
from app.models.card import Card
from app.models.card_metadata import Archetype, Attribute, Color, Keyword
from app.models.card_printing import CardPrinting
from app.models.card_set import CardSet
from app.repositories import card_repo
from app.schemas.card_search import CardSearchFilters


class AsyncDbBridge:
    def __init__(self, session: Session):
        self.session = session

    async def scalar(self, query):
        return self.session.scalar(query)

    async def scalars(self, query):
        return self.session.scalars(query)


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        op01 = CardSet(id=1, code="OP01", name="First set", sort_order=1)
        op02 = CardSet(id=2, code="OP02", name="Second set", sort_order=2)
        red = Color(name="Red")
        green = Color(name="Green")
        card = Card(
            id=1, code="OP01-001", name="Sample Card", original_set=op01,
            card_type="Character", cost=1, power=6000, counter=1000,
            colors=[red, green], attributes=[Attribute(name="Slash")],
            archetypes=[Archetype(name="Straw Hat Crew")],
            keywords=[Keyword(name="Rush")],
        )
        session.add(
            CardPrinting(card=card, product_set=op01, variant_code="regular", rarity="R", block_icon="X")
        )
        session.add(op02)
        session.commit()
        yield AsyncDbBridge(session)
    engine.dispose()


def check(db, **kwargs):
    cards, total = asyncio.run(
        card_repo.list_filtered(db, limit=20, offset=0, filters=CardSearchFilters(**kwargs))
    )
    return [c.code for c in cards], total


def test_lowercase_colors_and_set_with_or_and_and(db):
    assert check(db, colors=("red", "yellow"), sets=("op01",), costs=(1,)) == (["OP01-001"], 1)
    assert check(db, colors=("blue", "red"), sets=("op01",)) == (["OP01-001"], 1)
    assert check(db, colors=("red",), sets=("op02",)) == ([], 0)


def test_mixed_case_and_whitespace_in_text_filters(db):
    assert check(
        db,
        colors=(" RED ",), card_types=(" cHaRaCtEr ",),
        attributes=(" slASH ",), keywords=(" rUsH ",),
        archetypes=(" straw HAT crew ",), sets=(" Op01 ",),
    ) == (["OP01-001"], 1)


def test_case_insensitive_printing_options_same_printing(db):
    assert check(db, rarities=("r",), variants=("REGULAR",), block_icons=("x",)) == (["OP01-001"], 1)
    assert check(db, rarities=("sR",)) == ([], 0)


def test_counter_casefold_in_repository(db):
    assert check(db, counter_values=("1000",)) == (["OP01-001"], 1)
    assert check(db, counter_values=("NONE", "1000")) == (["OP01-001"], 1)
    assert check(db, counter_values=("NONE",)) == ([], 0)


def test_counter_none_case_insensitive_in_http_validation():
    app = create_app()
    async def fake_db():
        yield object()
    app.dependency_overrides[get_db] = fake_db
    with patch.object(card_repo, "list_filtered", new_callable=AsyncMock) as mocked:
        mocked.return_value = ([], 0)
        with TestClient(app) as client:
            response = client.get("/cards?counter_values=NONE")
        assert response.status_code == 200, response.text
        assert mocked.await_args.kwargs["filters"].counter_values == ("NONE",)
