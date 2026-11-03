"""HTTP rute za korisničku kolekciju (predavanje 4)."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.collection import CollectionEntryResponse
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
