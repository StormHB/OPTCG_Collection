"""Regresije transakcija kolekcije i posudbi na zasebnom PostgreSQL servisu."""

import asyncio
from contextlib import asynccontextmanager
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import Workbook
from sqlalchemy import delete, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.errors import AppError
from app.core.test_database import inspect_migration_connection
from app.models import Card, CardPrinting, CardSet, CollectionEntry, User
from app.repositories.collection_repo import get_for_user_and_printing
from app.schemas.card_loan import CardLoanCreate, CardLoanReturn
from app.schemas.collection import CollectionEntryUpdate
from app.services import card_loan_service, collection_service
from app.services.collection_excel_import import apply_plan, build_plan

pytestmark = pytest.mark.postgres


@asynccontextmanager
async def _verified_session(engine):
    async with engine.begin() as connection:
        await connection.run_sync(inspect_migration_connection)
        await connection.execute(text("SET LOCAL statement_timeout = '15s'"))
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            yield session


@asynccontextmanager
async def _loan_data(url):
    engine = create_async_engine(url)
    tag = uuid4().hex
    try:
        async with _verified_session(engine) as session:
            owner = User(username=f"loan_11c2_{tag}", password_hash="test-only")
            card_set = CardSet(code=f"T{tag[:11]}", name="Test 11C.2", sort_order=1)
            card = Card(code=f"T{tag[:19]}", name="Test card", original_set=card_set)
            printing = CardPrinting(card=card, product_set=card_set)
            session.add_all([owner, printing])
            await session.flush()
            session.add(
                CollectionEntry(user_id=owner.id, printing_id=printing.id, quantity=3)
            )
            await session.flush()
        try:
            yield engine, owner, printing.id
        finally:
            async with _verified_session(engine) as session:
                # Brisanje vlasnika kaskadno cisti samo njegove posudbe i kolekciju.
                await session.execute(delete(User).where(User.id == owner.id))
                await session.execute(
                    delete(CardPrinting).where(CardPrinting.id == printing.id)
                )
                await session.execute(delete(Card).where(Card.id == card.id))
                await session.execute(delete(CardSet).where(CardSet.id == card_set.id))
    finally:
        await engine.dispose()


async def _wait_for_row_lock(first, first_pid, second_pid, competing_task):
    async with asyncio.timeout(5):
        while not competing_task.done():
            blocking_pids = await first.scalar(
                text("SELECT pg_blocking_pids(:pid)"), {"pid": second_pid}
            )
            if first_pid in blocking_pids:
                return
            await asyncio.sleep(0.02)
    pytest.fail("Druga transakcija dovrsila se bez cekanja na PostgreSQL lock")


async def _run_competing_operations(engine, first_operation, second_operation):
    async with _verified_session(engine) as second:
        second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
        competing_task = None
        try:
            async with _verified_session(engine) as first:
                first_pid = await first.scalar(text("SELECT pg_backend_pid()"))
                assert first_pid != second_pid
                await first_operation(first)
                competing_task = asyncio.create_task(second_operation(second))
                await _wait_for_row_lock(first, first_pid, second_pid, competing_task)
            # Prva transakcija je commitana i druga sada moze nastaviti.
            await asyncio.wait_for(competing_task, timeout=5)
        finally:
            if competing_task is not None:
                competing_task.cancel()
                await asyncio.gather(competing_task, return_exceptions=True)


async def _quantity_import_plan(session, owner_id, printing_id):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "VARIJANTE"
    sheet.append(["ID izdanja", "Kolicina"])
    sheet.append([printing_id, 1])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    plan = await build_plan(
        session, owner_id, buffer.getvalue(), "test.xlsx", "replace"
    )
    assert not plan.errors
    return plan


def test_two_concurrent_loans_cannot_exceed_owned_quantity(postgres_database_url):
    async def exercise():
        async with _loan_data(postgres_database_url) as (engine, owner, printing_id):
            request = CardLoanCreate(
                printing_id=printing_id,
                direction="lent",
                person_name="Test",
                quantity=2,
            )

            async def lend(session):
                return await card_loan_service.create_loan(
                    session, owner, owner.id, request
                )

            with pytest.raises(AppError) as rejected:
                await _run_competing_operations(engine, lend, lend)
            assert rejected.value.status_code == 409
            assert rejected.value.code == "insufficient_quantity"

            async with _verified_session(engine) as session:
                loans = await card_loan_service.list_loans(session, owner, owner.id)
                assert [loan.outstanding_quantity for loan in loans] == [2]

    asyncio.run(exercise())


def test_two_concurrent_returns_cannot_over_return_a_loan(postgres_database_url):
    async def exercise():
        async with _loan_data(postgres_database_url) as (engine, owner, printing_id):
            request = CardLoanCreate(
                printing_id=printing_id,
                direction="lent",
                person_name="Test",
                quantity=3,
            )
            async with _verified_session(engine) as session:
                loan = await card_loan_service.create_loan(
                    session, owner, owner.id, request
                )

            async def partial_return(session):
                return await card_loan_service.return_loan(
                    session, owner, owner.id, loan.id, CardLoanReturn(quantity=2)
                )

            with pytest.raises(AppError) as rejected:
                await _run_competing_operations(engine, partial_return, partial_return)
            assert rejected.value.status_code == 409
            assert rejected.value.code == "return_exceeds_outstanding"

            async with _verified_session(engine) as session:
                saved = await card_loan_service.get_loan(
                    session, owner, owner.id, loan.id
                )
                assert saved.quantity_returned == 2
                assert saved.outstanding_quantity == 1
                assert saved.returned_at is None

    asyncio.run(exercise())


def test_note_patch_reports_missing_entry_after_concurrent_delete(
    postgres_database_url,
):
    async def exercise():
        async with _loan_data(postgres_database_url) as (engine, owner, printing_id):

            async def delete_entry(session):
                await collection_service.delete_collection_entry(
                    session, owner, owner.id, printing_id
                )

            async def patch_note(session):
                await collection_service.update_collection_entry(
                    session,
                    owner,
                    owner.id,
                    printing_id,
                    CollectionEntryUpdate(note="Nova napomena"),
                )

            with pytest.raises(AppError) as rejected:
                await _run_competing_operations(engine, delete_entry, patch_note)
            assert rejected.value.status_code == 404
            assert rejected.value.code == "not_found"

            async with _verified_session(engine) as session:
                assert (
                    await get_for_user_and_printing(session, owner.id, printing_id)
                    is None
                )

    asyncio.run(exercise())


@pytest.mark.parametrize("mutation", ["patch", "delete", "excel"])
def test_new_loan_blocks_competing_collection_reduction(
    postgres_database_url, mutation
):
    async def exercise():
        async with _loan_data(postgres_database_url) as (engine, owner, printing_id):
            request = CardLoanCreate(
                printing_id=printing_id,
                direction="lent",
                person_name="Test",
                quantity=2,
            )
            if mutation == "excel":
                async with _verified_session(engine) as session:
                    plan = await _quantity_import_plan(session, owner.id, printing_id)

            async def lend(session):
                await card_loan_service.create_loan(session, owner, owner.id, request)

            async def reduce_quantity(session):
                if mutation == "patch":
                    await collection_service.update_collection_entry(
                        session,
                        owner,
                        owner.id,
                        printing_id,
                        CollectionEntryUpdate(quantity=1),
                    )
                elif mutation == "delete":
                    await collection_service.delete_collection_entry(
                        session, owner, owner.id, printing_id
                    )
                else:
                    await apply_plan(session, plan, plan.token)

            with pytest.raises(AppError) as rejected:
                await _run_competing_operations(engine, lend, reduce_quantity)
            assert rejected.value.status_code == 409
            assert rejected.value.code == "active_loans_exceed_owned"

            async with _verified_session(engine) as session:
                entry = await get_for_user_and_printing(session, owner.id, printing_id)
                assert entry is not None and entry.quantity == 3
                loans = await card_loan_service.list_loans(session, owner, owner.id)
                assert [loan.outstanding_quantity for loan in loans] == [2]

    asyncio.run(exercise())


@pytest.mark.parametrize("mutation", ["patch", "delete"])
def test_excel_apply_rejects_collection_edit_during_wait(
    postgres_database_url, mutation
):
    async def exercise():
        async with _loan_data(postgres_database_url) as (engine, owner, printing_id):
            async with _verified_session(engine) as session:
                plan = await _quantity_import_plan(session, owner.id, printing_id)

            async def edit_collection(session):
                if mutation == "patch":
                    await collection_service.update_collection_entry(
                        session,
                        owner,
                        owner.id,
                        printing_id,
                        CollectionEntryUpdate(note="Napomena nakon pregleda"),
                    )
                else:
                    await collection_service.delete_collection_entry(
                        session, owner, owner.id, printing_id
                    )

            async def import_collection(session):
                await apply_plan(session, plan, plan.token)

            with pytest.raises(AppError) as rejected:
                await _run_competing_operations(
                    engine, edit_collection, import_collection
                )
            assert rejected.value.status_code == 409
            assert rejected.value.code == "stale_import_preview"

            async with _verified_session(engine) as session:
                entry = await get_for_user_and_printing(session, owner.id, printing_id)
                if mutation == "patch":
                    assert entry is not None
                    assert entry.quantity == 3
                    assert entry.note == "Napomena nakon pregleda"
                else:
                    assert entry is None

    asyncio.run(exercise())


def test_late_postgres_error_rolls_back_collection_and_loan(postgres_database_url):
    async def exercise():
        async with _loan_data(postgres_database_url) as (engine, owner, printing_id):
            with pytest.raises(DBAPIError) as rejected:
                async with _verified_session(engine) as session:
                    await collection_service.update_collection_entry(
                        session,
                        owner,
                        owner.id,
                        printing_id,
                        CollectionEntryUpdate(quantity=4),
                    )
                    request = CardLoanCreate(
                        printing_id=printing_id,
                        direction="lent",
                        person_name="Test",
                        quantity=4,
                    )
                    loan = await card_loan_service.create_loan(
                        session, owner, owner.id, request
                    )
                    assert loan.id and loan.outstanding_quantity == 4
                    await session.execute(text("SELECT 1 / 0"))
            assert rejected.value.orig.sqlstate == "22012"

            async with _verified_session(engine) as session:
                entry = await get_for_user_and_printing(session, owner.id, printing_id)
                assert entry is not None and entry.quantity == 3
                assert (
                    await card_loan_service.list_loans(session, owner, owner.id) == []
                )

    asyncio.run(exercise())
