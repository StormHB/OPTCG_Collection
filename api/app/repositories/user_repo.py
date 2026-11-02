from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_by_id(
    db: AsyncSession,
    user_id: int
) -> User | None:
    return await db.get(User, user_id)


async def get_by_username(
    db: AsyncSession,
    username: str
) -> User | None:
    result = await db.execute(
        select(User).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    user: User
) -> User:
    db.add(user)
    await db.flush()
    return user