"""Proizvod/set: OP, EB, ST, PRB, promo itd."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CardSet(Base):
    __tablename__ = "card_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(nullable=False)

    # Izvorna pripadnost broja karte: OP01-001 -> OP01.
    original_cards: Mapped[list[Card]] = relationship(back_populates="original_set")
    # Fizička izdanja koja se nalaze u proizvodu/setu (uklj. PRB reprintove).
    printings: Mapped[list[CardPrinting]] = relationship(back_populates="product_set")
