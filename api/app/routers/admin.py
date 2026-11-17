"""Administratorske rute; pristup se provjerava u FastAPI ovisnosti."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import db_session_dependency
from app.core.permissions import require_role
from app.repositories import admin_repo
from app.schemas.error import error_responses
from app.schemas.user import UserResponse

router = APIRouter()


@router.get(
    "/users",
    response_model=list[UserResponse],
    dependencies=[Depends(require_role("admin"))],
    responses=error_responses(401, 403, 422),
)
async def list_users(
    db: AsyncSession = db_session_dependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[UserResponse]:
    """Prikazi korisnike administratoru, bez hashiranih lozinki."""
    return await admin_repo.list_users(db, limit=limit, offset=offset)
