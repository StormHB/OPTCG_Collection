"""Poslovna pravila za osobne kolekcije (predavanje 4)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.collection_entry import CollectionEntry
from app.models.user import User
from app.repositories import collection_repo


def ensure_collection_owner(current_user: User, owner_user_id: int) -> None:
    """Odbij pristup tuđoj kolekciji, uključujući i administratora.

    Admin upravlja zajedničkim katalogom, ali nema automatski pristup
    privatnim kolekcijama drugih korisnika.
    """
    if current_user.id != owner_user_id:
        raise AppError("forbidden", "Nemate pristup tudoj kolekciji", 403)


async def get_user_collection(
    db: AsyncSession, current_user: User, owner_user_id: int
) -> list[CollectionEntry]:
    """Prvo provjeri vlasništvo, a tek onda čitaj kolekciju iz baze."""
    ensure_collection_owner(current_user, owner_user_id)
    return await collection_repo.list_for_user(db, owner_user_id)
