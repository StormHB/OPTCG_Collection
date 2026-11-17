"""Privatni API za pregled i uređivanje osobne kolekcije."""

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import db_session_dependency, get_current_user
from app.models.user import User
from app.routers.card_loans import router as card_loans_router
from app.routers.collection_import import router as collection_import_router
from app.schemas.collection import (
    CollectionEntryCreate,
    CollectionEntryResponse,
    CollectionEntryUpdate,
)
from app.schemas.collection_stats import CollectionStatsResponse
from app.schemas.error import error_responses
from app.services import collection_service, collection_stats_service

router = APIRouter()


@router.get(
    "/{user_id}",
    response_model=list[CollectionEntryResponse],
    responses=error_responses(401, 403, 422),
)
async def get_collection(
    user_id: int = Path(ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=2_147_483_647),
    db: AsyncSession = db_session_dependency,
    current_user: User = Depends(get_current_user),
):
    """Dohvati korisnikove zapise, ali samo ako je prijavljen kao vlasnik."""
    return await collection_service.get_user_collection(
        db, current_user, user_id, limit=limit, offset=offset
    )


@router.get(
    "/{user_id}/stats",
    response_model=CollectionStatsResponse,
    tags=["collection-stats"],
    responses=error_responses(401, 403, 422),
)
async def get_collection_stats(
    user_id: int = Path(ge=1),
    db: AsyncSession = db_session_dependency,
    current_user: User = Depends(get_current_user),
):
    """Ukupne količine, broj različitih izdanja i dovršeni playsetovi."""
    return await collection_stats_service.get_collection_stats(
        db, current_user, user_id
    )


@router.post(
    "/{user_id}/entries",
    response_model=CollectionEntryResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 403, 404, 409, 422),
)
async def add_collection_entry(
    body: CollectionEntryCreate,
    user_id: int = Path(ge=1),
    db: AsyncSession = db_session_dependency,
    current_user: User = Depends(get_current_user),
):
    """Dodaj fizičko izdanje u vlastitu kolekciju."""
    return await collection_service.add_collection_entry(
        db, current_user, user_id, body
    )


@router.patch(
    "/{user_id}/entries/{printing_id}",
    response_model=CollectionEntryResponse,
    responses=error_responses(401, 403, 404, 409, 422),
)
async def update_collection_entry(
    body: CollectionEntryUpdate,
    user_id: int = Path(ge=1),
    printing_id: int = Path(ge=1),
    db: AsyncSession = db_session_dependency,
    current_user: User = Depends(get_current_user),
):
    """Ažuriraj quantity i/ili note jednog izdanja."""
    return await collection_service.update_collection_entry(
        db, current_user, user_id, printing_id, body
    )


@router.delete(
    "/{user_id}/entries/{printing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 403, 404, 409, 422),
)
async def delete_collection_entry(
    user_id: int = Path(ge=1),
    printing_id: int = Path(ge=1),
    db: AsyncSession = db_session_dependency,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Ukloni zapis iz svoje kolekcije, bez brisanja karte iz kataloga."""
    await collection_service.delete_collection_entry(
        db, current_user, user_id, printing_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Unutar već registriranog /collections routera: bez promjene app/main.py.

router.include_router(collection_import_router)

# Korak 9B: posudbe su dodatni privatni endpointovi istog /collections routera.

router.include_router(card_loans_router)
