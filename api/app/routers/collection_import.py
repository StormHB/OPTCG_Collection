"""Autentificirani preview i potvrđeni uvoz osobnog Excel workbooks."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import db_session_dependency, get_current_user
from app.core.errors import AppError
from app.models.user import User
from app.schemas.collection_import import (
    CollectionImportApplyResponse,
    CollectionImportPreviewResponse,
)
from app.schemas.error import error_responses
from app.services.collection_excel_import import (
    MAX_UPLOAD_BYTES,
    apply_plan,
    build_plan,
)
from app.services.collection_service import ensure_collection_owner

router = APIRouter()


async def _read_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise AppError("invalid_excel", "Pošalji .xlsx datoteku", 422)
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()
    if not content:
        raise AppError("invalid_excel", "Excel datoteka ne smije biti prazna", 422)
    if len(content) > MAX_UPLOAD_BYTES:
        raise AppError(
            "excel_too_large", "Excel datoteka ne smije biti veća od 6 MB", 413
        )
    return content


@router.post(
    "/{user_id}/import/preview",
    response_model=CollectionImportPreviewResponse,
    responses=error_responses(401, 403, 413, 422),
)
async def preview_collection_import(
    file: Annotated[UploadFile, File(description="Excel s osobnim količinama")],
    user_id: int = Path(ge=1),
    mode: Literal["replace", "add"] = Query(default="replace"),
    db: AsyncSession = db_session_dependency,
    current_user: User = Depends(get_current_user),
):
    """Ne mijenja bazu. Vraća preview i token za identičan idući apply."""
    ensure_collection_owner(current_user, user_id)
    content = await _read_upload(file)
    plan = await build_plan(db, user_id, content, file.filename, mode)
    return plan.summary()


@router.post(
    "/{user_id}/import/apply",
    response_model=CollectionImportApplyResponse,
    responses=error_responses(401, 403, 409, 413, 422),
)
async def apply_collection_import(
    file: Annotated[UploadFile, File(description="Ista Excel datoteka kao za preview")],
    user_id: int = Path(ge=1),
    plan_token: str = Query(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "SHA-256 token iz preview odgovora, vezan uz datoteku, mode, korisnika "
            "i relevantno stanje kolekcije; nije JWT i nema vremenski rok."
        ),
    ),
    mode: Literal["replace", "add"] = Query(default="replace"),
    db: AsyncSession = db_session_dependency,
    current_user: User = Depends(get_current_user),
):
    """Primjena u jednoj transakciji, samo ako preview još odgovara stanju baze."""
    ensure_collection_owner(current_user, user_id)
    content = await _read_upload(file)
    plan = await build_plan(db, user_id, content, file.filename, mode)
    return await apply_plan(db, plan, plan_token)
