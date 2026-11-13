"""Korak 9B: vlasništvo, dostupnost, djelomično i potpuno vraćanje."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.card_loan import CardLoan
from app.models.user import User
from app.repositories import card_loan_repo
from app.schemas.card_loan import CardLoanCreate, CardLoanResponse, CardLoanReturn
from app.services.collection_service import ensure_collection_owner


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _serialize(loan: CardLoan) -> CardLoanResponse:
    printing = loan.printing
    return CardLoanResponse(
        id=loan.id,
        user_id=loan.user_id,
        printing_id=loan.printing_id,
        direction=loan.direction,
        person_name=loan.person_name,
        quantity=loan.quantity,
        quantity_returned=loan.quantity_returned,
        outstanding_quantity=loan.quantity - loan.quantity_returned,
        loaned_at=_utc(loan.loaned_at),
        due_at=_utc(loan.due_at) if loan.due_at else None,
        returned_at=_utc(loan.returned_at) if loan.returned_at else None,
        note=loan.note,
        card_code=printing.card.code,
        card_name=printing.card.name,
        set_code=printing.product_set.code,
        variant_code=printing.variant_code,
        image_url=printing.image_url,
    )


async def list_loans(
    db: AsyncSession, current_user: User, user_id: int,
    *, direction: str | None = None, active_only: bool = False,
) -> list[CardLoanResponse]:
    ensure_collection_owner(current_user, user_id)
    loans = await card_loan_repo.list_for_owner(
        db, user_id, direction=direction, active_only=active_only
    )
    return [_serialize(loan) for loan in loans]


async def get_loan(
    db: AsyncSession, current_user: User, user_id: int, loan_id: int
) -> CardLoanResponse:
    ensure_collection_owner(current_user, user_id)
    loan = await card_loan_repo.get_for_owner(db, user_id, loan_id)
    if loan is None:
        raise AppError("loan_not_found", "Posudba nije pronadena", 404)
    return _serialize(loan)


async def create_loan(
    db: AsyncSession, current_user: User, user_id: int, data: CardLoanCreate
) -> CardLoanResponse:
    ensure_collection_owner(current_user, user_id)
    loaned_at = _utc(data.loaned_at) if data.loaned_at else datetime.now(timezone.utc)
    due_at = _utc(data.due_at) if data.due_at else None
    if due_at is not None and due_at < loaned_at:
        raise AppError("invalid_loan_dates", "Rok vracanja ne moze biti prije datuma posudbe", 422)
    if not await card_loan_repo.printing_exists(db, data.printing_id):
        raise AppError("printing_not_found", "Izdanje karte nije pronadeno", 404)

    if data.direction == "lent":
        # Najprije zaključaj owned redak; tek nakon toga zbroji aktivne posudbe.
        owned = await card_loan_repo.owned_quantity_locked(db, user_id, data.printing_id)
        outstanding = await card_loan_repo.outstanding_lent(db, user_id, data.printing_id)
        available = max(0, owned - outstanding)
        if data.quantity > available:
            raise AppError(
                "insufficient_quantity",
                f"Nije moguce posuditi {data.quantity} primjeraka; dostupno je {available}",
                409,
            )

    loan = CardLoan(
        user_id=user_id,
        printing_id=data.printing_id,
        direction=data.direction,
        person_name=data.person_name,
        quantity=data.quantity,
        quantity_returned=0,
        loaned_at=loaned_at,
        due_at=due_at,
        note=data.note,
    )
    await card_loan_repo.create(db, loan)
    loaded = await card_loan_repo.get_for_owner(db, user_id, loan.id)
    assert loaded is not None  # flush je upravo kreirao ovaj ID u istoj transakciji.
    return _serialize(loaded)


async def return_loan(
    db: AsyncSession, current_user: User, user_id: int,
    loan_id: int, data: CardLoanReturn,
) -> CardLoanResponse:
    ensure_collection_owner(current_user, user_id)
    loan = await card_loan_repo.get_for_owner(db, user_id, loan_id, lock=True)
    if loan is None:
        raise AppError("loan_not_found", "Posudba nije pronadena", 404)

    outstanding = loan.quantity - loan.quantity_returned
    if outstanding == 0:
        raise AppError("loan_already_returned", "Posudba je vec potpuno vracena", 409)
    if data.quantity > outstanding:
        raise AppError(
            "return_exceeds_outstanding",
            f"Nije moguce vratiti {data.quantity} primjeraka; preostalo je {outstanding}",
            409,
        )
    returned_at = _utc(data.returned_at) if data.returned_at else datetime.now(timezone.utc)
    if returned_at < _utc(loan.loaned_at):
        raise AppError("invalid_return_date", "Datum vracanja ne moze biti prije posudbe", 422)

    loan.quantity_returned += data.quantity
    if loan.quantity_returned == loan.quantity:
        loan.returned_at = returned_at
    await card_loan_repo.flush(db)
    return _serialize(loan)
