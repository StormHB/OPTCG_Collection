"""Poslovna pravila za osobne kolekcije (vlasništvo, jedinstvenost, količine)."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.collection_entry import CollectionEntry
from app.models.user import User
from app.repositories import collection_repo
from app.schemas.collection import CollectionEntryCreate, CollectionEntryUpdate


def ensure_collection_owner(current_user: User, owner_user_id: int) -> None:
    """Ni administrator ne dobiva automatski pristup tuđoj kolekciji."""
    if current_user.id != owner_user_id:
        raise AppError("forbidden", "Nemate pristup tudoj kolekciji", 403)


async def get_user_collection(
    db: AsyncSession, current_user: User, owner_user_id: int
) -> list[CollectionEntry]:
    ensure_collection_owner(current_user, owner_user_id)
    return await collection_repo.list_for_user(db, owner_user_id)


async def add_collection_entry(
    db: AsyncSession,
    current_user: User,
    owner_user_id: int,
    data: CollectionEntryCreate,
) -> CollectionEntry:
    """Izdanje mora postojati; isti korisnik ga smije dodati samo jednom."""
    ensure_collection_owner(current_user, owner_user_id)

    if not await collection_repo.printing_exists(db, data.printing_id):
        raise AppError("not_found", "Izdanje karte nije pronadeno", 404)

    existing = await collection_repo.get_for_user_and_printing(
        db, owner_user_id, data.printing_id
    )
    if existing is not None:
        raise AppError("conflict", "Izdanje je vec u kolekciji", 409)

    try:
        return await collection_repo.create_entry(
            db, owner_user_id, data.printing_id, data.quantity, data.note
        )
    except IntegrityError:
        # Dodatna zaštita od dva paralelna zahtjeva za isto izdanje.
        # get_db() će nakon iznimke napraviti rollback transakcije.
        raise AppError("conflict", "Nije moguce dodati izdanje u kolekciju", 409) from None


async def update_collection_entry(
    db: AsyncSession,
    current_user: User,
    owner_user_id: int,
    printing_id: int,
    data: CollectionEntryUpdate,
) -> CollectionEntry:
    ensure_collection_owner(current_user, owner_user_id)
    entry = await collection_repo.get_for_user_and_printing(
        db, owner_user_id, printing_id
    )
    if entry is None:
        raise AppError("not_found", "Zapis kolekcije nije pronaden", 404)

    # exclude_unset: note izostavljen -> ostaje; note=null -> briše se.
    changes = data.model_dump(exclude_unset=True)
    return await collection_repo.update_entry(db, entry, changes)


async def delete_collection_entry(
    db: AsyncSession,
    current_user: User,
    owner_user_id: int,
    printing_id: int,
) -> None:
    ensure_collection_owner(current_user, owner_user_id)
    entry = await collection_repo.get_for_user_and_printing(
        db, owner_user_id, printing_id
    )
    if entry is None:
        raise AppError("not_found", "Zapis kolekcije nije pronaden", 404)
    await collection_repo.delete_entry(db, entry)
