"""Pristup collection_entries; provjera prava ostaje u servisnom sloju."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.repositories import card_loan_repo

from app.models.card_printing import CardPrinting
from app.models.collection_entry import CollectionEntry


async def list_for_user(db: AsyncSession, user_id: int) -> list[CollectionEntry]:
    """Postojeći GET kolekcije iz predavanja 4."""
    result = await db.scalars(
        select(CollectionEntry)
        .where(CollectionEntry.user_id == user_id)
        .order_by(CollectionEntry.id)
    )
    return list(result.all())


async def printing_exists(db: AsyncSession, printing_id: int) -> bool:
    """Ne stvaraj kolekcijski zapis za nepostojeće fizičko izdanje."""
    result = await db.scalar(
        select(CardPrinting.id).where(CardPrinting.id == printing_id)
    )
    return result is not None


async def get_for_user_and_printing(
    db: AsyncSession, user_id: int, printing_id: int
) -> CollectionEntry | None:
    """Istodobno ograniči upit na vlasnika i na izdanje."""
    return await db.scalar(
        select(CollectionEntry).where(
            CollectionEntry.user_id == user_id,
            CollectionEntry.printing_id == printing_id,
        )
    )


async def create_entry(
    db: AsyncSession, user_id: int, printing_id: int, quantity: int, note: str | None
) -> CollectionEntry:
    entry = CollectionEntry(
        user_id=user_id,
        printing_id=printing_id,
        quantity=quantity,
        note=note,
    )
    db.add(entry)
    await db.flush()  # ID se generira prije slanja HTTP odgovora.
    return entry


async def update_entry(
    db: AsyncSession, entry: CollectionEntry, changes: dict
) -> CollectionEntry:
    """Mijenjaj samo polja koja su bila poslana u PATCH zahtjevu."""
    if "quantity" in changes:
        # Zakljucaj redak cak i ako kolicina raste: stanje iz prvog citanja
        # moze biti zastarjelo nakon paralelnog zahtjeva.
        locked = await db.scalar(
            select(CollectionEntry).where(CollectionEntry.id == entry.id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if locked is None:
            raise AppError("not_found", "Zapis kolekcije nije pronaden", 404)
        lent = await card_loan_repo.outstanding_lent(db, entry.user_id, entry.printing_id)
        if changes["quantity"] < lent:
            raise AppError(
                "active_loans_exceed_owned",
                f"Kolicina ne moze biti {changes['quantity']}; {lent} primjeraka je jos posudeno",
                409,
            )
    for field, value in changes.items():
        setattr(entry, field, value)
    await db.flush()
    return entry


async def delete_entry(db: AsyncSession, entry: CollectionEntry) -> None:
    await db.scalar(select(CollectionEntry.id).where(CollectionEntry.id == entry.id).with_for_update())
    lent = await card_loan_repo.outstanding_lent(db, entry.user_id, entry.printing_id)
    if lent:
        raise AppError("active_loans_exceed_owned", "Nije moguce obrisati izdanje s aktivnim posudbama", 409)
    await db.delete(entry)
    await db.flush()
