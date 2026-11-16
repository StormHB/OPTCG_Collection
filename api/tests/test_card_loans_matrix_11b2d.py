"""Korak 11B.2D: integrirana matrica posudbi na izoliranom SQLiteu."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Base, Card, CardPrinting, CardSet, CollectionEntry, User
from app.models.card_loan import CardLoan
from app.repositories import card_loan_repo
from app.schemas.card_loan import CardLoanCreate, CardLoanReturn
from app.services import card_loan_service

STAMP = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class DbAdapter:
    def __init__(self, session):
        self.session = session
        self.events = []
        self.statements = []

    async def scalar(self, statement):
        sql = str(statement.compile(dialect=postgresql.dialect()))
        if "FOR UPDATE" in sql and "collection_entries" in sql:
            self.events.append("owned_lock")
        elif "sum" in sql.lower() and "card_loans" in sql:
            self.events.append("outstanding")
        self.statements.append(statement)
        return self.session.scalar(statement)

    async def scalars(self, statement):
        self.statements.append(statement)
        return self.session.scalars(statement)

    async def execute(self, statement):
        self.statements.append(statement)
        return self.session.execute(statement)

    def add(self, item):
        self.session.add(item)

    async def flush(self):
        self.session.flush()


@pytest.fixture()
def loan_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        card_set = CardSet(code="OP01", name="Romance Dawn", sort_order=1)
        card = Card(code="OP01-016", name="Nami", original_set=card_set)
        printing = CardPrinting(
            card=card,
            product_set=card_set,
            variant_code="regular",
            image_url="https://example.org/nami.png",
        )
        owner = User(username="loan_owner", password_hash="unused", role="user")
        other = User(username="loan_other", password_hash="unused", role="user")
        session.add_all([printing, owner, other])
        session.flush()
        entry = CollectionEntry(
            user_id=owner.id, printing_id=printing.id, quantity=5, note="owned"
        )
        first = CardLoan(
            user_id=owner.id,
            printing_id=printing.id,
            direction="lent",
            person_name="Ivan",
            quantity=3,
            quantity_returned=1,
            loaned_at=STAMP,
        )
        second = CardLoan(
            user_id=owner.id,
            printing_id=printing.id,
            direction="lent",
            person_name="Maja",
            quantity=2,
            quantity_returned=0,
            loaned_at=STAMP + timedelta(hours=1),
        )
        borrowed = CardLoan(
            user_id=owner.id,
            printing_id=printing.id,
            direction="borrowed",
            person_name="Robin",
            quantity=10,
            quantity_returned=0,
            loaned_at=STAMP,
        )
        session.add_all([entry, first, second, borrowed])
        session.commit()
        yield DbAdapter(session), session, owner, other, printing, entry, first, second
    engine.dispose()


def run(coroutine):
    return asyncio.run(coroutine)


def _new_lent(printing_id, quantity):
    return CardLoanCreate(
        printing_id=printing_id,
        direction="lent",
        person_name="Zoro",
        quantity=quantity,
        loaned_at=STAMP + timedelta(days=1),
    )


def test_multiple_active_lent_loans_share_one_availability_limit(loan_db):
    db, session, owner, _, printing, _, _, _ = loan_db
    assert run(card_loan_repo.outstanding_lent(db, owner.id, printing.id)) == 4
    before = session.scalar(select(func.count()).select_from(CardLoan))
    with pytest.raises(AppError) as raised:
        run(
            card_loan_service.create_loan(
                db, owner, owner.id, _new_lent(printing.id, 2)
            )
        )
    assert raised.value.status_code == 409
    assert raised.value.code == "insufficient_quantity"
    assert session.scalar(select(func.count()).select_from(CardLoan)) == before
    assert db.events[-2:] == ["owned_lock", "outstanding"]


def test_partial_return_releases_availability_without_changing_owned_quantity(loan_db):
    db, session, owner, _, printing, entry, first, _ = loan_db
    returned = run(
        card_loan_service.return_loan(
            db,
            owner,
            owner.id,
            first.id,
            CardLoanReturn(quantity=1, returned_at=STAMP + timedelta(days=2)),
        )
    )
    assert returned.outstanding_quantity == 1
    assert run(card_loan_repo.outstanding_lent(db, owner.id, printing.id)) == 3
    assert entry.quantity == 5

    created = run(
        card_loan_service.create_loan(db, owner, owner.id, _new_lent(printing.id, 2))
    )
    assert created.quantity == 2
    assert run(card_loan_repo.outstanding_lent(db, owner.id, printing.id)) == 5
    assert entry.quantity == 5
    assert session.scalar(select(CollectionEntry.quantity)) == 5


def test_borrowed_loan_does_not_change_owned_or_outstanding_lent(loan_db):
    db, session, owner, _, printing, entry, *_ = loan_db
    before_owned = entry.quantity
    before_lent = run(card_loan_repo.outstanding_lent(db, owner.id, printing.id))
    response = run(
        card_loan_service.create_loan(
            db,
            owner,
            owner.id,
            CardLoanCreate(
                printing_id=printing.id,
                direction="borrowed",
                person_name="Sanji",
                quantity=100,
                loaned_at=STAMP,
            ),
        )
    )
    assert response.direction == "borrowed"
    assert entry.quantity == before_owned
    assert session.scalar(select(CollectionEntry.quantity)) == before_owned
    assert (
        run(card_loan_repo.outstanding_lent(db, owner.id, printing.id)) == before_lent
    )


def test_repository_scopes_loan_id_to_owner(loan_db):
    db, _, owner, other, _, _, first, _ = loan_db
    assert run(card_loan_repo.get_for_owner(db, owner.id, first.id)) is first
    assert run(card_loan_repo.get_for_owner(db, other.id, first.id)) is None


def test_sequential_returns_cannot_exceed_original_quantity(loan_db):
    db, _, owner, _, _, entry, first, _ = loan_db
    first.quantity_returned = 0
    first.returned_at = None
    first_result = run(
        card_loan_service.return_loan(
            db, owner, owner.id, first.id, CardLoanReturn(quantity=2)
        )
    )
    assert first_result.quantity_returned == 2
    with pytest.raises(AppError) as raised:
        run(
            card_loan_service.return_loan(
                db, owner, owner.id, first.id, CardLoanReturn(quantity=2)
            )
        )
    assert raised.value.status_code == 409
    assert raised.value.code == "return_exceeds_outstanding"
    assert first.quantity_returned == 2
    assert entry.quantity == 5


def test_full_return_closes_loan_and_second_return_is_rejected(loan_db):
    db, _, owner, _, _, entry, first, _ = loan_db
    result = run(
        card_loan_service.return_loan(
            db,
            owner,
            owner.id,
            first.id,
            CardLoanReturn(quantity=2, returned_at=STAMP + timedelta(days=3)),
        )
    )
    assert result.outstanding_quantity == 0
    assert result.returned_at == STAMP + timedelta(days=3)
    with pytest.raises(AppError) as raised:
        run(
            card_loan_service.return_loan(
                db, owner, owner.id, first.id, CardLoanReturn(quantity=1)
            )
        )
    assert raised.value.code == "loan_already_returned"
    assert entry.quantity == 5


def test_return_repository_query_locks_exact_owner_loan(loan_db):
    db, _, owner, _, _, _, first, _ = loan_db
    db.statements.clear()
    locked = run(card_loan_repo.get_for_owner(db, owner.id, first.id, lock=True))
    assert locked is first
    sql = str(db.statements[-1].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE OF card_loans" in sql
    assert "card_loans.user_id" in sql
    assert "card_loans.id" in sql
