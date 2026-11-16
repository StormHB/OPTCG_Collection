"""Korak 11B.1: matrica upita kataloga i ugovor za Counter dropdown.

SQLite testni katalog: ne koristi stvarni PostgreSQL ni osobne podatke.
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
from app.models.collection_entry import CollectionEntry
from app.models.user import User
from app.repositories import card_repo
from app.schemas.card_search import CardSearchFilters
from app.services import card_service


class SQLiteBridge:
    def __init__(self, session: Session):
        self.session = session

    async def scalar(self, statement):
        return self.session.scalar(statement)

    async def scalars(self, statement):
        return self.session.scalars(statement)


def _query(db, **filters):
    selection = CardSearchFilters(**filters)
    rows, total = asyncio.run(
        card_repo.list_filtered(db, limit=100, offset=0, filters=selection)
    )
    return [c.code for c in rows], total


@pytest.fixture()
def matrix_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        op01, op02, eb03, st01, prb01, don = [
            CardSet(code=code, name=code, sort_order=i)
            for i, code in enumerate(
                ("OP01", "OP02", "EB03", "ST01", "PRB01", "DON"), start=1
            )
        ]
        red = Color(name="Red")
        blue = Color(name="Blue")
        green = Color(name="Green")
        yellow = Color(name="Yellow")
        slash = Attribute(name="Slash")
        strike = Attribute(name="Strike")
        straw = Archetype(name="Straw Hat Crew")
        wb = Archetype(name="Whitebeard Pirates")
        rush = Keyword(name="Rush")
        blocker = Keyword(name="Blocker")

        def card(code, name, set_, kind, cost, power, counter, **many):
            return Card(
                code=code,
                name=name,
                original_set=set_,
                card_type=kind,
                cost=cost,
                power=power,
                counter=counter,
                **many,
            )

        c1 = card(
            "OP01-001",
            "Luffy 100%_Pilot",
            op01,
            "Character",
            1,
            6000,
            1000,
            colors=[red, blue],
            attributes=[slash],
            archetypes=[straw],
            keywords=[rush],
        )
        c2 = card(
            "OP01-002",
            "Yellow Marine",
            op01,
            "Character",
            2,
            5000,
            2000,
            colors=[yellow],
            attributes=[strike],
            archetypes=[wb],
            keywords=[blocker],
        )
        c3 = card(
            "OP02-001",
            "Green Leader",
            op02,
            "Leader",
            5,
            5000,
            None,
            colors=[green],
            attributes=[slash],
            archetypes=[straw],
        )
        c4 = card(
            "EB03-001",
            "EB Special",
            eb03,
            "Event",
            0,
            0,
            0,
            colors=[red],
        )
        c5 = card(
            "ST01-001",
            "Starter",
            st01,
            "Character",
            3,
            7000,
            1000,
            colors=[blue],
            attributes=[strike],
        )
        c6 = card("DON-001", "DON!!", don, "DON!!", None, None, None)
        c7 = card("OP02-002", "Wildcard A_B%", op02, "Event", 0, 0, None)

        def printing(c, set_, variant, rarity, block):
            return CardPrinting(
                card=c,
                product_set=set_,
                variant_code=variant,
                rarity=rarity,
                block_icon=block,
            )

        p1 = printing(c1, op01, "regular", "R", "1")
        p1_reprint = printing(c1, prb01, "regular", "UC", "2")
        printing(c1, op01, "manga", "SR", "3")
        p2 = printing(c2, op01, "regular", "SR", "1")
        p3 = printing(c3, op02, "regular", "L", "2")
        printing(c4, eb03, "regular", "C", "X")
        p5 = printing(c5, st01, "regular", "UC", "1")
        p6 = printing(c6, don, "regular", "DON!!", None)
        printing(c7, op02, "regular", "C", None)
        owner = User(username="owner", password_hash="unused", role="user")
        other = User(username="other", password_hash="unused", role="user")
        session.add_all([owner, other])
        session.flush()
        session.add_all([c1, c2, c3, c4, c5, c6, c7])
        session.flush()
        session.add_all(
            [
                CollectionEntry(user_id=owner.id, printing_id=p1.id, quantity=4),
                CollectionEntry(
                    user_id=owner.id, printing_id=p1_reprint.id, quantity=0
                ),
                CollectionEntry(user_id=owner.id, printing_id=p2.id, quantity=2),
                CollectionEntry(user_id=owner.id, printing_id=p3.id, quantity=1),
                CollectionEntry(user_id=owner.id, printing_id=p6.id, quantity=10),
                CollectionEntry(user_id=other.id, printing_id=p5.id, quantity=4),
            ]
        )
        session.commit()
        yield SQLiteBridge(session), owner.id, other.id
    engine.dispose()


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("colors", " rEd ", ["EB03-001", "OP01-001"]),
        ("colors", " BLUE ", ["OP01-001", "ST01-001"]),
        ("card_types", " chArAcTeR ", ["OP01-001", "OP01-002", "ST01-001"]),
        ("attributes", " sLAsH ", ["OP01-001", "OP02-001"]),
        ("keywords", " RUSH ", ["OP01-001"]),
        ("archetypes", " STRAW HAT CREW ", ["OP01-001", "OP02-001"]),
        ("rarities", " sR ", ["OP01-001", "OP01-002"]),
        (
            "variants",
            " ReGulaR ",
            [
                "DON-001",
                "EB03-001",
                "OP01-001",
                "OP01-002",
                "OP02-001",
                "OP02-002",
                "ST01-001",
            ],
        ),
        ("block_icons", " x ", ["EB03-001"]),
        ("sets", " OP-01 ", ["OP01-001", "OP01-002"]),
        ("sets", " eB-03 ", ["EB03-001"]),
        ("sets", " sT-01 ", ["ST01-001"]),
        ("sets", " PrB-01 ", ["OP01-001"]),
        ("sets", " DON ", ["DON-001"]),
    ],
)
def test_text_filters_ignore_case_and_outer_spaces(matrix_db, field, value, expected):
    db, _, _ = matrix_db
    codes, total = _query(db, **{field: (value,)})
    assert codes == expected
    assert total == len(expected)


@pytest.mark.parametrize(
    ("filtering", "expected"),
    [
        ({"colors": ("red", "green"), "costs": (1, 5)}, ["OP01-001", "OP02-001"]),
        ({"colors": ("red", "red", " BLUE "), "costs": (1,)}, ["OP01-001"]),
        ({"attributes": ("Slash", "Strike"), "keywords": ("Rush",)}, ["OP01-001"]),
        (
            {"archetypes": ("Whitebeard Pirates", "Straw Hat Crew"), "powers": (5000,)},
            ["OP01-002", "OP02-001"],
        ),
        (
            {"sets": ("OP01", "PRB01"), "variants": ("regular",)},
            ["OP01-001", "OP01-002"],
        ),
        ({"sets": ("PRB01",), "rarities": ("SR",)}, []),
        ({"sets": ("PRB01",), "block_icons": ("1",)}, []),
        (
            {
                "sets": ("OP01",),
                "variants": ("manga",),
                "rarities": ("SR",),
                "block_icons": ("3",),
            },
            ["OP01-001"],
        ),
        (
            {"counter_values": ("0", "none")},
            ["DON-001", "EB03-001", "OP02-001", "OP02-002"],
        ),
        ({"counter_values": ("1000", "2000")}, ["OP01-001", "OP01-002", "ST01-001"]),
    ],
)
def test_or_within_and_and_between_categories(matrix_db, filtering, expected):
    db, _, _ = matrix_db
    codes, total = _query(db, **filtering)
    assert codes == expected
    assert total == len(expected)


@pytest.mark.parametrize(
    ("search", "expected"),
    [
        ("op-01", ["OP01-001", "OP01-002"]),
        ("op01", ["OP01-001", "OP01-002"]),
        ("EB-03", ["EB03-001"]),
        ("ST-01", ["ST01-001"]),
        ("100%", ["OP01-001"]),
        ("_", ["OP01-001", "OP02-002"]),
        ("A_B%", ["OP02-002"]),
        ("random_card", []),
        (" LUFfY ", ["OP01-001"]),
    ],
)
def test_search_alias_case_spaces_and_literal_wildcards(matrix_db, search, expected):
    db, _, _ = matrix_db
    codes, total = _query(db, search=search)
    assert codes == expected
    assert total == len(expected)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("colors", "orange"),
        ("card_types", "Alien"),
        ("attributes", "Flying"),
        ("keywords", "Teleport"),
        ("archetypes", "Unknown Clan"),
        ("sets", "OP-99"),
        ("rarities", "XYZ"),
        ("variants", "unknown"),
        ("block_icons", "Z"),
    ],
)
def test_unknown_text_filter_returns_empty_page_not_error(matrix_db, field, value):
    db, _, _ = matrix_db
    assert _query(db, **{field: (value,)}) == ([], 0)


def test_repeated_printing_filters_must_match_same_reprint(matrix_db):
    db, _, _ = matrix_db
    assert _query(db, sets=("PRB01",), rarities=("UC",), variants=("regular",)) == (
        ["OP01-001"],
        1,
    )
    assert _query(db, sets=("PRB01",), rarities=("R",)) == ([], 0)


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        (
            {"collection_statuses": ("owned",)},
            ["DON-001", "OP01-001", "OP01-002", "OP02-001"],
        ),
        ({"collection_statuses": ("playset",)}, ["DON-001", "OP01-001", "OP02-001"]),
        ({"collection_statuses": ("missing",), "sets": ("ST01",)}, ["ST01-001"]),
        ({"collection_statuses": ("owned",), "sets": ("PRB01",)}, []),
        ({"collection_statuses": ("missing",), "sets": ("PRB01",)}, ["OP01-001"]),
        ({"collection_statuses": ("playset",), "sets": ("OP01",)}, ["OP01-001"]),
        (
            {"collection_statuses": ("missing", "playset"), "sets": ("OP01",)},
            ["OP01-001"],
        ),
    ],
)
def test_private_status_filters_respect_printings_and_owner(
    matrix_db, selection, expected
):
    db, owner_id, _ = matrix_db
    selection["collection_user_id"] = owner_id
    codes, total = _query(db, **selection)
    assert codes == expected
    assert total == len(expected)


def test_other_users_playsets_not_owned_by_current_user(matrix_db):
    db, _, other_id = matrix_db
    assert _query(
        db, collection_statuses=("playset",), collection_user_id=other_id
    ) == (["ST01-001"], 1)


def test_pagination_total_and_stable_order(matrix_db):
    db, _, _ = matrix_db
    page = CardSearchFilters(colors=("Red", "Blue", "Yellow"))
    first, total = asyncio.run(
        card_repo.list_filtered(db, limit=2, offset=0, filters=page)
    )
    second, second_total = asyncio.run(
        card_repo.list_filtered(db, limit=2, offset=2, filters=page)
    )
    assert [c.code for c in first] == ["EB03-001", "OP01-001"]
    assert [c.code for c in second] == ["OP01-002", "ST01-001"]
    assert total == second_total == 4


def _http_client():
    app = create_app()

    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    return TestClient(app)


@pytest.mark.parametrize(
    "query",
    [
        "costs=11",
        "costs=-1",
        "costs=1.5",
        "costs=abc",
        "powers=13001",
        "powers=-1",
        "powers=NaN",
        "powers=3.5",
        "counter_values=none",
        "counter_values=3000",
        "counter_values=1000.0",
        "counter_missing=unknown",
        "limit=0",
        "limit=101",
        "offset=-1",
        "collection_status=unknown",
        "search=" + "x" * 121,
    ],
)
def test_invalid_http_query_rejected_before_repository(query):
    with patch.object(card_repo, "list_filtered", new_callable=AsyncMock) as repo:
        result = _http_client().get(f"/cards?{query}")
        assert result.status_code == 422, result.text
        assert result.json()["code"] == "validation_error"
        repo.assert_not_awaited()


def test_counter_dropdown_always_matches_http_contract():
    db_options = {
        "sets": [],
        "colors": [],
        "attributes": [],
        "archetypes": [],
        "keywords": [],
        "card_types": [],
        "costs": [],
        "powers": [],
        "counter_values": [None, 0, 1000, 2000, 3000],
        "rarities": [],
        "variants": [],
        "block_icons": [],
    }
    with patch.object(card_repo, "get_filter_values", new_callable=AsyncMock) as repo:
        repo.return_value = db_options
        data = asyncio.run(card_service.get_card_filters(object()))
        assert data.counter_values == [0, 1000, 2000]
        assert None not in data.counter_values
        assert 3000 not in data.counter_values

    schema = create_app().openapi()
    parameters = schema["paths"]["/cards"]["get"]["parameters"]
    selection = next(p for p in parameters if p["name"] == "counter_values")
    item_schema = selection["schema"]
    if "items" not in item_schema:
        item_schema = next(p for p in item_schema["anyOf"] if p.get("type") == "array")
    item = item_schema["items"]
    if "$ref" in item:
        item = schema["components"]["schemas"][item["$ref"].rsplit("/", 1)[-1]]
    assert item["enum"] == ["0", "1000", "2000"]


def test_public_filter_options_contain_no_collection_information():
    schema = create_app().openapi()
    public = schema["components"]["schemas"]["CardFilterOptionsResponse"]
    assert "collection_status" not in public["properties"]
    assert "collection_user_id" not in public["properties"]
