"""Količina jednog fizičkog izdanja u kolekciji određenog korisnika."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CollectionEntry(Base):
    __tablename__ = "collection_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "printing_id", name="uq_user_printing"),
        CheckConstraint("quantity >= 0", name="ck_collection_quantity_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    printing_id: Mapped[int] = mapped_column(
        ForeignKey("card_printings.id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(nullable=False, server_default="0")
    note: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="collection_entries")
    printing: Mapped[CardPrinting] = relationship(back_populates="collection_entries")
