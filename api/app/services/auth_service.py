"""Poslovna logika autentikacije. Ovdje nema FastAPI ruta."""

from jwt import InvalidTokenError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.jwt import create_access_token, create_refresh_token, decode_token
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories import user_repo

INVALID_CREDENTIALS = "Neispravno korisnicko ime ili lozinka"
_DUMMY_HASH = hash_password("dummy-password-for-timing")


async def register_user(db: AsyncSession, username: str, password: str) -> User:
    if await user_repo.get_by_username(db, username) is not None:
        raise AppError("username_taken", "Korisnicko ime je zauzeto", 409)

    # Uloga NIKAD ne dolazi iz registracijskog zahtjeva.
    user = User(username=username, password_hash=hash_password(password), role="user")
    try:
        await user_repo.create(db, user)  # flush, ne commit
    except IntegrityError:
        # UNIQUE ogranicenje baze stiti i od istodobne registracije istog usernamea.
        # get_db ce zbog AppError napraviti rollback transakcije.
        raise AppError("username_taken", "Korisnicko ime je zauzeto", 409) from None
    return user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User:
    user = await user_repo.get_by_username(db, username)
    candidate_hash = user.password_hash if user else _DUMMY_HASH
    password_ok = verify_password(password, candidate_hash)
    if user is None or not password_ok or not user.is_active:
        raise AppError("invalid_credentials", INVALID_CREDENTIALS, 401)
    return user


def create_tokens(user: User) -> tuple[str, str]:
    return create_access_token(user.id, user.role), create_refresh_token(user.id)


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    try:
        payload = decode_token(refresh_token)
    except InvalidTokenError:
        raise AppError("invalid_credentials", "Neispravan refresh token", 401) from None

    if payload.get("type") != "refresh":
        raise AppError("invalid_credentials", "Neispravan refresh token", 401)

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise AppError("invalid_credentials", "Neispravan refresh token", 401) from None

    user = await user_repo.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise AppError("invalid_credentials", "Neispravan refresh token", 401)
    return create_tokens(user)
