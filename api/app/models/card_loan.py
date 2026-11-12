"""Evidencija posudbi tocnog fizickog izdanja karte (Korak 9A).

Kolicina u collection_entries prikazuje vlasnistvo; posudbe ne mijenjaju taj broj.
Pravila dostupne kolicine i autorizacije implementiraju se u servisu (Korak 9B).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.card_printing import CardPrinting
    from app.models.user import User


def utc_now() -> datetime:
    """Vremenska oznaka sa zonom u UTC-u (bez datetime.utcnow())."""
    return datetime.now(timezone.utc)


class CardLoan(Base):
    """Jedan dogovor o posudbi; vracanje moze biti djelomicno ili potpuno."""

    __tablename__ = "card_loans"
    __table_args__ = (
        CheckConstraint("direction IN ('lent', 'borrowed')", name="ck_card_loans_direction"),
        CheckConstraint("quantity > 0", name="ck_card_loans_quantity_positive"),
        CheckConstraint(
            "quantity_returned >= 0 AND quantity_returned <= quantity",
            name="ck_card_loans_returned_range",
        ),
        CheckConstraint("length(trim(person_name)) > 0", name="ck_card_loans_person_nonblank"),
        Index("ix_card_loans_user_direction", "user_id", "direction"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    printing_id: Mapped[int] = mapped_column(
        ForeignKey("card_printings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    person_name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    quantity_returned: Mapped[int] = mapped_column(nullable=False, server_default="0")

    loaned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    # Ne diramo postojece modele User/CardPrinting; jednostrane veze su dovoljne.
    user: Mapped[User] = relationship("User")
    printing: Mapped[CardPrinting] = relationship("CardPrinting")

    @property
    def outstanding_quantity(self) -> int:
        """Broj primjeraka koji jos nisu vraceni."""
        return self.quantity - self.quantity_returned
