"""Provjera pravila CRUD-a na stvarnim SQLAlchemy modelima (SQLite u memoriji)."""

import asyncio

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, Card, CardPrinting, CardSet, CollectionEntry, User
from app.repositories import collection_repo
from app.schemas.collection import CollectionEntryCreate, CollectionEntryUpdate
from app.services import collection_service


class AsyncAdapter:
    """Jednostavan adapter za testiranje asinkronog repozitorija nad SQLite sesijom."""

    def __init__(self, session):
        self.session = session

    async def scalar(self, query):
        return self.session.scalar(query)

    async def scalars(self, query):
        return self.session.scalars(query)

    def add(self, obj):
        self.session.add(obj)

    async def flush(self):
        self.session.flush()

    async def delete(self, obj):
        self.session.delete(obj)


def test_create_update_delete_preserves_catalog_and_other_users():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        op01 = CardSet(code="OP01", name="OP01", sort_order=1)
        card = Card(code="OP01-016", name="Nami", original_set=op01)
        printing = CardPrinting(card=card, product_set=op01, variant_code="regular")
        user = User(username="owner", password_hash="unused", role="user")
        other = User(username="other", password_hash="unused", role="user")
        session.add_all([printing, user, other])
        session.commit()

        db = AsyncAdapter(session)
        entry = asyncio.run(collection_service.add_collection_entry(
            db, user, user.id,
            CollectionEntryCreate(printing_id=printing.id, quantity=0, note="za razmjenu"),
        ))
        session.commit()
        assert entry.id is not None and entry.quantity == 0
        assert len(asyncio.run(collection_repo.list_for_user(db, other.id))) == 0

        entry = asyncio.run(collection_service.update_collection_entry(
            db, user, user.id, printing.id,
            CollectionEntryUpdate(quantity=4),
        ))
        session.commit()
        assert entry.quantity == 4 and entry.note == "za razmjenu"

        entry = asyncio.run(collection_service.update_collection_entry(
            db, user, user.id, printing.id,
            CollectionEntryUpdate(note=None),
        ))
        session.commit()
        assert entry.note is None

        asyncio.run(collection_service.delete_collection_entry(db, user, user.id, printing.id))
        session.commit()
        assert session.scalars(select(CollectionEntry)).all() == []
        assert session.scalars(select(CardPrinting)).all() == [printing]
        assert session.scalars(select(Card)).all() == [card]
    engine.dispose()
