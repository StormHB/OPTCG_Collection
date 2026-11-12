"""Autentificirani preview i potvrđeni uvoz osobnog Excel workbooks."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.collection_excel_import import (
    MAX_UPLOAD_BYTES,
    apply_plan,
    build_plan,
)
from app.services.collection_service import ensure_collection_owner
from app.core.errors import AppError

router = APIRouter()


async def _read_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise AppError("invalid_excel", "Pošalji .xlsx datoteku", 422)
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise AppError("invalid_excel", "Excel ne smije biti prazan ili veći od 6 MB", 422)
    return content


@router.post("/{user_id}/import/preview")
async def preview_collection_import(
    file: Annotated[UploadFile, File(description="Excel s osobnim količinama")],
    user_id: int = Path(ge=1),
    mode: Literal["replace", "add"] = Query(default="replace"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ne mijenja bazu. Vraća preview i token za identičan idući apply."""
    ensure_collection_owner(current_user, user_id)
    content = await _read_upload(file)
    plan = await build_plan(db, user_id, content, file.filename, mode)
    return plan.summary()


@router.post("/{user_id}/import/apply")
async def apply_collection_import(
    file: Annotated[UploadFile, File(description="Ista Excel datoteka kao za preview")],
    user_id: int = Path(ge=1),
    plan_token: str = Query(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
    mode: Literal["replace", "add"] = Query(default="replace"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Primjena u jednoj transakciji, samo ako preview još odgovara stanju baze."""
    ensure_collection_owner(current_user, user_id)
    content = await _read_upload(file)
    plan = await build_plan(db, user_id, content, file.filename, mode)
    return await apply_plan(db, plan, plan_token)
