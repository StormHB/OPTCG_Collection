"""Korak 10B: autentikacija samo kada /cards traži osobne podatke.

Obični GET /cards ostaje javan čak i ako klijent šalje zastarjeli JWT.
"""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User

_optional_bearer = HTTPBearer(auto_error=False)


async def get_collection_filter_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Bez osobnih filtera nema potrebe dohvaćati ni validirati korisnika.

    Kod osobnog filtera koristi se ista provjera JWT-a kao za sve ostale
    privatne rute, uključujući tip tokena i status aktivnosti korisnika.
    """
    if "collection_status" not in request.query_params:
        return None
    if credentials is None:
        return None
    return await get_current_user(credentials=credentials, db=db)
