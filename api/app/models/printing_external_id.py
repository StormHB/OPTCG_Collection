"""Vanjski identifikatori iz kataloga (TCGplayer, OPlayTCG, Binder Pirates...)."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class PrintingExternalId(Base):
    __tablename__ = "printing_external_ids"
    __table_args__ = (
        UniqueConstraint(
            "source", "external_id", "language", "finish",
            name="uq_printing_external_source_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    printing_id: Mapped[int] = mapped_column(
        ForeignKey("card_printings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="unknown"
    )
    finish: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default="unknown"
    )

    printing: Mapped[CardPrinting] = relationship(back_populates="external_ids")
