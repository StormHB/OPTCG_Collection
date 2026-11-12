"""Jedinstveni kartični identitet (npr. OP01-001), neovisno o ilustraciji."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.card_metadata import (
    Archetype, Attribute, Color, Keyword,
    card_archetypes, card_attributes, card_colors, card_keywords,
)

class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    original_set_id: Mapped[int] = mapped_column(
        ForeignKey("card_sets.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    # Privremeno zadržavamo izvorna tekstualna polja: postojeći importi se ne kvare.
    color: Mapped[str | None] = mapped_column(String(40))
    card_type: Mapped[str | None] = mapped_column(String(30))
    cost: Mapped[int | None] = mapped_column(Integer)
    power: Mapped[int | None] = mapped_column(Integer)
    counter: Mapped[int | None] = mapped_column(Integer)
    attribute: Mapped[str | None] = mapped_column(String(100))
    affiliation_text: Mapped[str | None] = mapped_column(Text)
    effect_text: Mapped[str | None] = mapped_column(Text)
    life: Mapped[int | None] = mapped_column(Integer)  # Leader Life, inace NULL

    colors: Mapped[list[Color]] = relationship(secondary=card_colors)
    attributes: Mapped[list[Attribute]] = relationship(secondary=card_attributes)
    archetypes: Mapped[list[Archetype]] = relationship(secondary=card_archetypes)
    keywords: Mapped[list[Keyword]] = relationship(secondary=card_keywords)

    original_set: Mapped[CardSet] = relationship(back_populates="original_cards")
    printings: Mapped[list[CardPrinting]] = relationship(back_populates="card")
