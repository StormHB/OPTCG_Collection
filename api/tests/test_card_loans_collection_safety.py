"""Regresijski testovi: uredjivanje kolekcije i Excel ne smiju pregaziti posudbe."""

import asyncio
from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Base, Card, CardPrinting, CardSet, CollectionEntry, User
from app.models.card_loan import CardLoan
from app.repositories import collection_repo
from app.services.collection_excel_import import apply_plan, build_plan


class DbAdapter:
    def __init__(self, session):
        self.session = session

    async def scalar(self, statement):
        return self.session.scalar(statement)

    async def scalars(self, statement):
        return self.session.scalars(statement)

    async def execute(self, statement):
        return self.session.execute(statement)

    async def flush(self):
        self.session.flush()

    async def delete(self, item):
        self.session.delete(item)

    def add(self, item):
        self.session.add(item)


@pytest.fixture
def sample():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        st = CardSet(code="OP01", name="Romance Dawn", sort_order=1)
        c = Card(code="OP01-016", name="Nami", original_set=st)
        printing = CardPrinting(card=c, product_set=st, variant_code="regular")
        owner = User(username="owner_9b", password_hash="-", role="user")
        session.add_all([printing, owner])
        session.flush()
        entry = CollectionEntry(user_id=owner.id, printing_id=printing.id, quantity=5)
        loan = CardLoan(
            user_id=owner.id, printing_id=printing.id, direction="lent",
            person_name="Ivan", quantity=4, quantity_returned=1,
        )
        session.add_all([entry, loan])
        session.commit()
        yield DbAdapter(session), session, entry, loan, owner, printing
    engine.dispose()


def run(coroutine):
    return asyncio.run(coroutine)


def workbook(quantity):
    wb = Workbook()
    ws = wb.active
    ws.title = "OP01"
    ws.append(["Broj karte", "Količina"])
    ws.append(["OP01-016", quantity])
    b = BytesIO()
    wb.save(b)
    wb.close()
    return b.getvalue()


def test_cannot_reduce_owned_below_active_lending(sample):
    db, session, entry, loan, _, _ = sample
    with pytest.raises(AppError) as error:
        run(collection_repo.update_entry(db, entry, {"quantity": 2}))
    assert error.value.status_code == 409
    assert error.value.code == "active_loans_exceed_owned"
    assert entry.quantity == 5
    assert loan.quantity - loan.quantity_returned == 3


def test_reducing_to_exact_outstanding_is_allowed(sample):
    db, _, entry, _, _, _ = sample
    run(collection_repo.update_entry(db, entry, {"quantity": 3}))
    assert entry.quantity == 3


def test_delete_with_active_lending_is_forbidden(sample):
    db, session, entry, _, _, _ = sample
    with pytest.raises(AppError) as error:
        run(collection_repo.delete_entry(db, entry))
    assert error.value.status_code == 409
    assert session.scalar(select(CollectionEntry)) is entry


def test_borrowed_loans_do_not_reduce_owned_quantity(sample):
    db, session, entry, loan, _, _ = sample
    loan.direction = "borrowed"
    session.flush()
    run(collection_repo.update_entry(db, entry, {"quantity": 0}))
    assert entry.quantity == 0


def test_excel_preview_rejects_amount_below_outstanding_lent(sample):
    db, _, _, _, owner, _ = sample
    content = workbook(2)
    plan = run(build_plan(db, owner.id, content, "owned.xlsx", "replace"))
    assert plan.summary()["can_apply"] is False
    assert plan.summary()["error_count"] == 1
    assert plan.issues[-1].code == "active_loans_exceed_owned"
    with pytest.raises(AppError) as error:
        run(apply_plan(db, plan, plan.token))
    assert error.value.status_code == 422


def test_excel_preview_accepts_exact_outstanding(sample):
    db, session, entry, _, owner, _ = sample
    plan = run(build_plan(db, owner.id, workbook(3), "owned.xlsx", "replace"))
    assert plan.summary()["can_apply"] is True
    assert plan.summary()["update"] == 1
    run(apply_plan(db, plan, plan.token))
    assert entry.quantity == 3


def test_apply_detects_new_loan_created_after_preview(sample):
    db, session, entry, loan, owner, _ = sample
    # Preview valja: trenutno je aktivno 3, a u Excelu ostaju 3.
    plan = run(build_plan(db, owner.id, workbook(3), "owned.xlsx", "replace"))
    assert plan.summary()["can_apply"] is True
    # Netko je u medjuvremenu dodatno posudio jednu kartu.
    loan.quantity = 5
    session.flush()  # sada je 4 aktivno, ali collection quantity je jos 5
    with pytest.raises(AppError) as error:
        run(apply_plan(db, plan, plan.token))
    assert error.value.status_code == 409
    assert error.value.code == "active_loans_exceed_owned"
    assert entry.quantity == 5


def test_repository_reads_exact_printing_and_outstanding_in_sqlite(sample):
    from app.repositories import card_loan_repo
    from app.services.card_loan_service import get_loan, list_loans

    db, session, _, loan, owner, printing = sample
    assert run(card_loan_repo.outstanding_lent(db, owner.id, printing.id)) == 3
    assert run(card_loan_repo.owned_quantity_locked(db, owner.id, printing.id)) == 5

    listed = run(list_loans(db, owner, owner.id, active_only=True, direction="lent"))
    assert len(listed) == 1
    assert listed[0].printing_id == printing.id
    assert listed[0].card_code == "OP01-016"
    assert listed[0].set_code == "OP01"
    assert listed[0].outstanding_quantity == 3

    item = run(get_loan(db, owner, owner.id, loan.id))
    assert item.id == loan.id
    assert item.card_name == "Nami"


def test_borrowed_loan_is_not_counted_as_outstanding_lent(sample):
    from app.repositories import card_loan_repo

    db, session, _, loan, owner, printing = sample
    loan.direction = "borrowed"
    session.flush()
    assert run(card_loan_repo.outstanding_lent(db, owner.id, printing.id)) == 0


def test_active_only_excludes_fully_returned_loans(sample):
    from app.repositories import card_loan_repo

    db, session, _, loan, owner, _ = sample
    loan.quantity_returned = loan.quantity
    session.flush()
    assert run(card_loan_repo.list_for_owner(db, owner.id, active_only=True)) == []
    assert len(run(card_loan_repo.list_for_owner(db, owner.id, active_only=False))) == 1
