"""Registracija ORM modela za Alembic target_metadata."""
from app.core.database import Base
from app.models.card_metadata import (
    Archetype, Attribute, Color, Keyword,
    card_archetypes, card_attributes, card_colors, card_keywords,
)
from app.models.card import Card
from app.models.card_printing import CardPrinting
from app.models.card_set import CardSet
from app.models.collection_entry import CollectionEntry
from app.models.card_loan import CardLoan
from app.models.printing_external_id import PrintingExternalId
from app.models.user import User

__all__ = [
    "Base", "User", "CardSet", "Card", "CardPrinting", "CollectionEntry", "CardLoan",
    "Color", "Attribute", "Archetype", "Keyword", "PrintingExternalId",
    "card_colors", "card_attributes", "card_archetypes", "card_keywords",
]
