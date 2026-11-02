"""Jedinstveni kartični identitet (npr. OP01-001), neovisno o ilustraciji."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    original_set_id: Mapped[int] = mapped_column(
        ForeignKey("card_sets.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # Moguće višebojne karte, npr. "Red/Green". Kasnije možemo normalizirati.
    color: Mapped[str | None] = mapped_column(String(40))
    card_type: Mapped[str | None] = mapped_column(String(30))
    cost: Mapped[int | None] = mapped_column(Integer)
    power: Mapped[int | None] = mapped_column(Integer)
    counter: Mapped[int | None] = mapped_column(Integer)
    attribute: Mapped[str | None] = mapped_column(String(100))
    # Privremeno čuvamo izvorni tekst; precizne višestruke filtere modeliramo kasnije.
    affiliation_text: Mapped[str | None] = mapped_column(Text)
    effect_text: Mapped[str | None] = mapped_column(Text)

    original_set: Mapped[CardSet] = relationship(back_populates="original_cards")
    printings: Mapped[list[CardPrinting]] = relationship(back_populates="card")
