"""Upiti nad tablicom collection_entries; ovdje nema provjere prava."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection_entry import CollectionEntry


async def list_for_user(db: AsyncSession, user_id: int) -> list[CollectionEntry]:
    """Dohvati zapise kolekcije jednog korisnika sortirane po ID-u."""
    result = await db.scalars(
        select(CollectionEntry)
        .where(CollectionEntry.user_id == user_id)
        .order_by(CollectionEntry.id)
    )
    return list(result.all())
