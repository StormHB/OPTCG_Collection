"""Rječnici i M:N veze za filtriranje kataloga.

Svaka stavka rječnika postoji jednom. Povezne tablice dopuštaju više
vrijednosti na jednoj karti bez dupliciranja samog zapisa karte.
"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

card_colors = Table(
    "card_colors",
    Base.metadata,
    Column("card_id", ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True),
    Column("color_id", ForeignKey("colors.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_card_colors_color_id", "color_id"),
)

card_attributes = Table(
    "card_attributes",
    Base.metadata,
    Column("card_id", ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True),
    Column("attribute_id", ForeignKey("attributes.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_card_attributes_attribute_id", "attribute_id"),
)

card_archetypes = Table(
    "card_archetypes",
    Base.metadata,
    Column("card_id", ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True),
    Column("archetype_id", ForeignKey("archetypes.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_card_archetypes_archetype_id", "archetype_id"),
)

card_keywords = Table(
    "card_keywords",
    Base.metadata,
    Column("card_id", ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True),
    Column("keyword_id", ForeignKey("keywords.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_card_keywords_keyword_id", "keyword_id"),
)

class Color(Base):
    __tablename__ = "colors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)

class Attribute(Base):
    __tablename__ = "attributes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)

class Archetype(Base):
    __tablename__ = "archetypes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)

class Keyword(Base):
    __tablename__ = "keywords"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
