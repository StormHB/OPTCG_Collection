"""Fizičko izdanje: regular, alt art, manga, DON!! ilustracija, PRB reprint."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class CardPrinting(Base):
    __tablename__ = "card_printings"
    __table_args__ = (
        UniqueConstraint(
            "card_id", "product_set_id", "variant_code", name="uq_printing_identity"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id"), nullable=False, index=True
    )
    product_set_id: Mapped[int] = mapped_column(
        ForeignKey("card_sets.id"), nullable=False, index=True
    )
    variant_code: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="regular"
    )
    rarity: Mapped[str | None] = mapped_column(String(20))
    image_url: Mapped[str | None] = mapped_column(String(600))
    block_icon: Mapped[str | None] = mapped_column(String(2))

    card: Mapped[Card] = relationship(back_populates="printings")
    product_set: Mapped[CardSet] = relationship(back_populates="printings")
    collection_entries: Mapped[list[CollectionEntry]] = relationship(
        back_populates="printing"
    )
    external_ids: Mapped[list[PrintingExternalId]] = relationship(
        back_populates="printing", cascade="all, delete-orphan"
    )
