"""Zajednicke FastAPI ovisnosti: transakcija i trenutni korisnik."""

from collections.abc import AsyncIterator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.errors import AppError
from app.core.jwt import decode_token
from app.models.user import User
from app.repositories import user_repo


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# auto_error=False: sami vracamo dosljedan oblik pogreske (code, message).
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AppError("invalid_credentials", "Nedostaje access token", 401)

    try:
        payload = decode_token(credentials.credentials)
    except ExpiredSignatureError:
        raise AppError("token_expired", "Token je istekao", 401) from None
    except InvalidTokenError:
        raise AppError("invalid_credentials", "Neispravan token", 401) from None

    if payload.get("type") != "access":
        raise AppError("invalid_credentials", "Ocekivan je access token", 401)

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise AppError("invalid_credentials", "Neispravan token", 401) from None

    user = await user_repo.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AppError("invalid_credentials", "Neispravan token", 401)

    # User.role uzimamo iz aktualnog zapisa u bazi, ne vjerujemo staroj ulozi u JWT-u.
    return user
