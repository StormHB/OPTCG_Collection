"""Privatne rute evidencije posudbi pod /collections/{user_id}/loans."""

from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.card_loan import CardLoanCreate, CardLoanResponse, CardLoanReturn
from app.services import card_loan_service

router = APIRouter(prefix="/{user_id}/loans", tags=["loans"])


@router.get("", response_model=list[CardLoanResponse])
async def list_loans(
    user_id: int = Path(ge=1),
    direction: Literal["lent", "borrowed"] | None = Query(default=None),
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await card_loan_service.list_loans(
        db, current_user, user_id, direction=direction, active_only=active_only
    )


@router.post("", response_model=CardLoanResponse, status_code=status.HTTP_201_CREATED)
async def create_loan(
    body: CardLoanCreate,
    user_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await card_loan_service.create_loan(db, current_user, user_id, body)


@router.get("/{loan_id}", response_model=CardLoanResponse)
async def get_loan(
    user_id: int = Path(ge=1),
    loan_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await card_loan_service.get_loan(db, current_user, user_id, loan_id)


@router.post("/{loan_id}/returns", response_model=CardLoanResponse)
async def return_loan(
    body: CardLoanReturn,
    user_id: int = Path(ge=1),
    loan_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await card_loan_service.return_loan(db, current_user, user_id, loan_id, body)
