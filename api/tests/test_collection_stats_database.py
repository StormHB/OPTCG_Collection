"""Korak 10A: SQLAlchemy/SQLite provjera bez privatne PostgreSQL baze."""

import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Base,
    Card,
    CardLoan,
    CardPrinting,
    CardSet,
    CollectionEntry,
    User,
)
from app.repositories import collection_stats_repo
from app.services.collection_stats_service import get_collection_stats
from app.services.playset_service import is_playset, playset_category, playset_threshold


class AsyncAdapter:
    """SQLAlchemy upit je stvaran, samo je sesija sinkrona za SQLite test."""

    def __init__(self, session: Session):
        self.session = session
        self.calls = 0

    async def execute(self, stmt):
        self.calls += 1
        return self.session.execute(stmt)


def test_query_and_stats_count_only_owned_printings_not_loans():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        op01 = CardSet(code="OP01", name="Romance Dawn", sort_order=1)
        prb = CardSet(code="PRB01", name="Premium", sort_order=2)
        don_set = CardSet(code="DON", name="DON", sort_order=3)
        event = Card(
            code="OP01-010", name="Event", original_set=op01, card_type="Event"
        )
        nami = Card(
            code="OP01-016", name="Nami", original_set=op01, card_type="Character"
        )
        leader = Card(code="OP01-001", name="Leader", original_set=op01, card_type=None)
        don = Card(code="DON-001", name="DON", original_set=don_set, card_type=None)
        stage = Card(
            code="OP01-020", name="Stage", original_set=op01, card_type="Stage"
        )
        p1 = CardPrinting(
            card=nami, product_set=op01, variant_code="regular", rarity="R"
        )
        p2 = CardPrinting(
            card=nami, product_set=prb, variant_code="reprint", rarity="R"
        )
        p3 = CardPrinting(
            card=leader, product_set=op01, variant_code="regular", rarity="L"
        )
        p4 = CardPrinting(card=don, product_set=don_set, variant_code="regular")
        p5 = CardPrinting(card=stage, product_set=op01, variant_code="regular")
        p6 = CardPrinting(card=event, product_set=op01, variant_code="regular")
        user = User(username="owner", password_hash="hash", role="user")
        other = User(username="other", password_hash="hash", role="user")
        session.add_all([p1,p2,p3,p4,p5,p6,user,other])
        session.flush()
        session.add_all([
            CollectionEntry(user_id=user.id, printing_id=p1.id, quantity=4),
            CollectionEntry(user_id=user.id, printing_id=p2.id, quantity=8),
            CollectionEntry(user_id=user.id, printing_id=p3.id, quantity=1),
            CollectionEntry(user_id=user.id, printing_id=p4.id, quantity=10),
            CollectionEntry(user_id=user.id, printing_id=p5.id, quantity=3),
            CollectionEntry(user_id=user.id, printing_id=p6.id, quantity=0),
            CollectionEntry(user_id=other.id, printing_id=p1.id, quantity=99),
            CardLoan(
                user_id=user.id, printing_id=p1.id, direction="lent",
                person_name="Marko", quantity=2,
            ),
            CardLoan(
                user_id=user.id, printing_id=p2.id, direction="borrowed",
                person_name="Ivan", quantity=30,
            ),
        ])
        session.flush()

        db = AsyncAdapter(session)
        result = asyncio.run(get_collection_stats(db, user, user.id)).model_dump()
        assert result == {
            "user_id": user.id,
            "total_cards": 26,
            "distinct_printings": 5,
            "playsets": 4,
            "playsets_by_type": {"leader": 1, "don": 1, "other": 2},
        }
        assert db.calls == 1, "Izbjegavamo N+1 upite"
        assert asyncio.run(
            collection_stats_repo.load_owned_printings(db, other.id)
        ) == [
            (99, "Character", "R", "OP01", "OP01-016")
        ]
        assert asyncio.run(get_collection_stats(db, other, other.id)).playsets == 1
        # Read-only: upiti i izračun ne mogu mijenjati već spremljene podatke.
        assert session.get(CollectionEntry, 1).quantity == 4
        assert session.get(CollectionEntry, 6).quantity == 0
        assert session.get(CardLoan, 1).quantity_returned == 0
    engine.dispose()


def test_empty_collection_has_all_zeros():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(username="empty", password_hash="hash", role="user")
        session.add(user)
        session.flush()
        result = asyncio.run(get_collection_stats(AsyncAdapter(session), user, user.id))
        assert result.total_cards == 0
        assert result.distinct_printings == 0
        assert result.playsets == 0
        assert result.playsets_by_type.model_dump() == {
            "leader": 0, "don": 0, "other": 0
        }
    engine.dispose()


def test_playset_thresholds_and_fallbacks():
    assert playset_category(" Leader ") == "leader"
    assert playset_category(None, rarity="L") == "leader"
    assert playset_category(None, rarity="leader") == "leader"
    assert playset_category("don!!!") == "don"
    assert playset_category(None, set_code=" don ") == "don"
    assert playset_category(None, card_code="DON-EN001") == "don"
    assert playset_category(None) == "other"
    assert playset_threshold(None, rarity="L") == 1
    assert playset_threshold(None, set_code="DON") == 10
    assert playset_threshold(None, card_code="DON-004") == 10
    assert playset_threshold("Event") == 4
    assert not is_playset("Character", 3)
    assert is_playset("Character", 4)
    assert is_playset("Leader", 1)
    assert not is_playset("DON!!", 9)
    assert is_playset("DON!!", 10)
    # I osam istih karata broji se kao jedan dovršen playset, ne dva.
    assert playset_threshold("Character") == 4
