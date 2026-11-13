"""SQLAlchemy upiti za privatnu evidenciju posudbi.

Pri posuđivanju zaključavamo collection_entries redak u PostgreSQL-u.
Time dvije paralelne posudbe istog izdanja ne mogu obje koristiti istu zalihu.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.card_loan import CardLoan
from app.models.card_printing import CardPrinting
from app.models.collection_entry import CollectionEntry


LOAN_LOAD = (
    selectinload(CardLoan.printing).selectinload(CardPrinting.card),
    selectinload(CardLoan.printing).selectinload(CardPrinting.product_set),
)


async def printing_exists(db: AsyncSession, printing_id: int) -> bool:
    return await db.scalar(select(CardPrinting.id).where(CardPrinting.id == printing_id)) is not None


async def owned_quantity_locked(db: AsyncSession, user_id: int, printing_id: int) -> int:
    """Zaključavanje je važno: provjera i stvaranje posudbe su jedna transakcija."""
    quantity = await db.scalar(
        select(CollectionEntry.quantity)
        .where(CollectionEntry.user_id == user_id, CollectionEntry.printing_id == printing_id)
        .with_for_update()
    )
    return quantity if quantity is not None else 0


async def outstanding_lent(db: AsyncSession, user_id: int, printing_id: int) -> int:
    return int(await db.scalar(
        select(func.coalesce(func.sum(CardLoan.quantity - CardLoan.quantity_returned), 0))
        .where(
            CardLoan.user_id == user_id,
            CardLoan.printing_id == printing_id,
            CardLoan.direction == "lent",
        )
    ) or 0)


async def create(db: AsyncSession, loan: CardLoan) -> CardLoan:
    db.add(loan)
    await db.flush()
    return loan


async def get_for_owner(
    db: AsyncSession, user_id: int, loan_id: int, *, lock: bool = False
) -> CardLoan | None:
    statement = (
        select(CardLoan).options(*LOAN_LOAD)
        .where(CardLoan.id == loan_id, CardLoan.user_id == user_id)
    )
    if lock:
        statement = statement.with_for_update(of=CardLoan)
    return await db.scalar(statement)


async def list_for_owner(
    db: AsyncSession,
    user_id: int,
    *,
    direction: str | None = None,
    active_only: bool = False,
) -> list[CardLoan]:
    statement = (
        select(CardLoan).options(*LOAN_LOAD)
        .where(CardLoan.user_id == user_id)
        .order_by(CardLoan.loaned_at.desc(), CardLoan.id.desc())
    )
    if direction is not None:
        statement = statement.where(CardLoan.direction == direction)
    if active_only:
        statement = statement.where(CardLoan.quantity_returned < CardLoan.quantity)
    return list((await db.scalars(statement)).all())


async def flush(db: AsyncSession) -> None:
    await db.flush()
