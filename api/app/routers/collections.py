"""Privatni API za pregled i uređivanje osobne kolekcije."""

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.collection import (
    CollectionEntryCreate,
    CollectionEntryResponse,
    CollectionEntryUpdate,
)
from app.services import collection_service

router = APIRouter()


@router.get("/{user_id}", response_model=list[CollectionEntryResponse])
async def get_collection(
    user_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dohvati korisnikove zapise, ali samo ako je prijavljen kao vlasnik."""
    return await collection_service.get_user_collection(db, current_user, user_id)


@router.post(
    "/{user_id}/entries",
    response_model=CollectionEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_collection_entry(
    body: CollectionEntryCreate,
    user_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dodaj fizičko izdanje u vlastitu kolekciju."""
    return await collection_service.add_collection_entry(db, current_user, user_id, body)


@router.patch(
    "/{user_id}/entries/{printing_id}",
    response_model=CollectionEntryResponse,
)
async def update_collection_entry(
    body: CollectionEntryUpdate,
    user_id: int = Path(ge=1),
    printing_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ažuriraj quantity i/ili note jednog izdanja."""
    return await collection_service.update_collection_entry(
        db, current_user, user_id, printing_id, body
    )


@router.delete(
    "/{user_id}/entries/{printing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_collection_entry(
    user_id: int = Path(ge=1),
    printing_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Ukloni zapis iz svoje kolekcije, bez brisanja karte iz kataloga."""
    await collection_service.delete_collection_entry(db, current_user, user_id, printing_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Unutar već registriranog /collections routera: bez promjene app/main.py.
from app.routers.collection_import import router as collection_import_router

router.include_router(collection_import_router)

# Korak 9B: posudbe su dodatni privatni endpointovi istog /collections routera.
from app.routers.card_loans import router as card_loans_router

router.include_router(card_loans_router)
