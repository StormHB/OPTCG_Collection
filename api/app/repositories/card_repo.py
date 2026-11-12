"""SQLAlchemy upiti nad zajednickim katalogom karata."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.card import Card
from app.models.card_metadata import Archetype, Attribute, Color, Keyword
from app.models.card_printing import CardPrinting
from app.models.card_set import CardSet
from app.schemas.card_search import CardSearchFilters


async def list_paginated(
    db: AsyncSession, *, limit: int, offset: int
) -> tuple[list[Card], int]:
    """Vrati jednu stranicu karata i ukupan broj karata u katalogu."""
    total = await db.scalar(select(func.count()).select_from(Card))
    result = await db.scalars(
        select(Card).order_by(Card.code, Card.id).limit(limit).offset(offset)
    )
    return list(result.all()), int(total or 0)


async def get_by_id_with_details(db: AsyncSession, card_id: int) -> Card | None:
    """Učitaj kartu zajedno s M:N vezama i izdanjima, bez naknadnih lazy upita."""
    statement = (
        select(Card)
        .where(Card.id == card_id)
        .options(
            selectinload(Card.colors),
            selectinload(Card.attributes),
            selectinload(Card.archetypes),
            selectinload(Card.keywords),
            selectinload(Card.printings),
        )
    )
    return await db.scalar(statement)


async def _distinct_values(db: AsyncSession, column) -> list:
    """Vrati jedinstvene, ne-NULL vrijednosti jednog stupca."""
    statement = (
        select(column)
        .where(column.is_not(None))
        .distinct()
        .order_by(column)
    )
    return list((await db.scalars(statement)).all())


async def get_filter_values(db: AsyncSession) -> dict:
    """Popisi za filtere; nikada ne čitamo korisničke kolekcije."""
    sets_result = await db.scalars(
        select(CardSet).order_by(CardSet.sort_order, CardSet.code)
    )
    return {
        "sets": list(sets_result.all()),
        "colors": await _distinct_values(db, Color.name),
        "attributes": await _distinct_values(db, Attribute.name),
        "archetypes": await _distinct_values(db, Archetype.name),
        "keywords": await _distinct_values(db, Keyword.name),
        "card_types": await _distinct_values(db, Card.card_type),
        "costs": await _distinct_values(db, Card.cost),
        "powers": await _distinct_values(db, Card.power),
        "counter_values": await _distinct_values(db, Card.counter),
        "rarities": await _distinct_values(db, CardPrinting.rarity),
        "variants": await _distinct_values(db, CardPrinting.variant_code),
        "block_icons": await _distinct_values(db, CardPrinting.block_icon),
    }


def _normalized_text_values(values: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize query values without changing canonical database spelling.

    Repeated options stay OR values, and surrounding whitespace is ignored.
    """
    return tuple(dict.fromkeys(value.strip().lower() for value in values if value.strip()))


async def list_filtered(
    db: AsyncSession, *, limit: int, offset: int, filters: CardSearchFilters
) -> tuple[list[Card], int]:
    """Filtriraj katalog bez JOIN-dupliciranja karti, zatim napravi paginaciju.

    - IN() i .any() daju OR unutar jedne kategorije.
    - Zasebni where() uvjeti daju AND između kategorija.
    - Više uvjeta nad izdanjem mora zadovoljiti ISTI card_printings red.
    """
    conditions = []

    if filters.colors:
        conditions.append(Card.colors.any(func.lower(Color.name).in_(_normalized_text_values(filters.colors))))
    if filters.card_types:
        conditions.append(func.lower(Card.card_type).in_(_normalized_text_values(filters.card_types)))
    if filters.costs:
        conditions.append(Card.cost.in_(filters.costs))
    if filters.powers:
        conditions.append(Card.power.in_(filters.powers))
    if filters.attributes:
        conditions.append(Card.attributes.any(func.lower(Attribute.name).in_(_normalized_text_values(filters.attributes))))
    if filters.keywords:
        conditions.append(Card.keywords.any(func.lower(Keyword.name).in_(_normalized_text_values(filters.keywords))))
    if filters.archetypes:
        conditions.append(Card.archetypes.any(func.lower(Archetype.name).in_(_normalized_text_values(filters.archetypes))))

    if filters.counter_values:
        # NULL (nema tiskane Counter vrijednosti) nije isto što i 0.
        counter_tokens = _normalized_text_values(filters.counter_values)
        values = [int(v) for v in counter_tokens if v != "none"]
        counter_checks = []
        if values:
            counter_checks.append(Card.counter.in_(values))
        if "none" in counter_tokens:
            counter_checks.append(Card.counter.is_(None))
        conditions.append(or_(*counter_checks))

    # Čuvamo semantiku fizičkog izdanja: set, raritet, varijanta i block
    # moraju odgovarati istome printing zapisu, a ne različitim reprintovima.
    printing_checks = []
    if filters.sets:
        printing_checks.append(
            CardPrinting.product_set.has(func.lower(CardSet.code).in_(_normalized_text_values(filters.sets)))
        )
    if filters.rarities:
        printing_checks.append(func.lower(CardPrinting.rarity).in_(_normalized_text_values(filters.rarities)))
    if filters.variants:
        printing_checks.append(func.lower(CardPrinting.variant_code).in_(_normalized_text_values(filters.variants)))
    if filters.block_icons:
        printing_checks.append(func.lower(CardPrinting.block_icon).in_(_normalized_text_values(filters.block_icons)))
    if printing_checks:
        conditions.append(Card.printings.any(and_(*printing_checks)))

    if filters.search and filters.search.strip():
        # '%' i '_' iz korisničkog teksta tretiramo doslovno, ne kao SQL wildcards.
        query = (
            filters.search.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        term = f"%{query}%"
        conditions.append(
            or_(
                Card.code.ilike(term, escape="\\"),
                Card.name.ilike(term, escape="\\"),
            )
        )

    total_statement = select(func.count()).select_from(Card).where(*conditions)
    page_statement = (
        select(Card)
        .where(*conditions)
        .order_by(Card.code, Card.id)
        .limit(limit)
        .offset(offset)
    )
    total = await db.scalar(total_statement)
    cards = await db.scalars(page_statement)
    return list(cards.all()), int(total or 0)
