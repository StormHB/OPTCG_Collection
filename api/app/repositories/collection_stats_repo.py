"""Jedan upit za osobne količine i metapodatke potrebne za statistiku.

Posudbe se namjerno ne pridružuju: ne predstavljaju promjenu vlasništva.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.card_printing import CardPrinting
from app.models.card_set import CardSet
from app.models.collection_entry import CollectionEntry

# Količina, tip karte, rarity izdanja, set izdanja i kod osnovne karte.
OwnedPrintingRow = tuple[int, str | None, str | None, str, str]


async def load_owned_printings(
    db: AsyncSession, user_id: int
) -> list[OwnedPrintingRow]:
    """Samo pozitivne količine vlasnika, bez N+1 upita i bez posudbi."""
    stmt = (
        select(
            CollectionEntry.quantity,
            Card.card_type,
            CardPrinting.rarity,
            CardSet.code,
            Card.code,
        )
        .join(CardPrinting, CollectionEntry.printing_id == CardPrinting.id)
        .join(Card, CardPrinting.card_id == Card.id)
        .join(CardSet, CardPrinting.product_set_id == CardSet.id)
        .where(CollectionEntry.user_id == user_id, CollectionEntry.quantity > 0)
    )
    result = await db.execute(stmt)
    return [tuple(row) for row in result.all()]
