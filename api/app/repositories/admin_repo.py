"""Citanje korisnika za administratorski pregled."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def list_users(db: AsyncSession, limit: int, offset: int) -> list[User]:
    """Vrati stranicu korisnika, stabilno sortiranu prema ID-u."""
    result = await db.execute(
        select(User).order_by(User.id).limit(limit).offset(offset)
    )
    return list(result.scalars().all())
