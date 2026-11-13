"""Servis za citanje kataloga; kasnije dodajemo filtre."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.repositories import card_repo
from app.schemas.card import (
    CardDetailResponse,
    CardFilterOptionsResponse,
    CardPageResponse,
    CardPrintingResponse,
    CardSetFilterOption,
    CardSummaryResponse,
)
from app.schemas.card_search import CardSearchFilters


async def get_cards(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    filters: CardSearchFilters | None = None,
) -> CardPageResponse:
    """Dohvati stranicu i pripremi javni odgovor bez ORM objekata."""
    # Odgovoran je i servis, ne samo HTTP ruta: nema privatnog upita
    # bez autentificiranog vlasničkog identiteta.
    if (
        filters is not None
        and filters.collection_statuses
        and filters.collection_user_id is None
    ):
        raise AppError(
            "invalid_credentials",
            "Za osobne filtere potreban je access token",
            401,
        )
    if filters is not None and filters.is_active():
        cards, total = await card_repo.list_filtered(
            db, limit=limit, offset=offset, filters=filters
        )
    else:
        cards, total = await card_repo.list_paginated(db, limit=limit, offset=offset)
    return CardPageResponse(
        items=[CardSummaryResponse.model_validate(card) for card in cards],
        total=total,
        limit=limit,
        offset=offset,
    )


async def get_card_detail(db: AsyncSession, *, card_id: int) -> CardDetailResponse:
    """Vrati jednu kartu ili standardni 404 ako ID ne postoji."""
    card = await card_repo.get_by_id_with_details(db, card_id)
    if card is None:
        raise AppError("not_found", "Karta nije pronadena", 404)

    # Osnovna polja su vec definirana u sazetku pa ih ne dupliciramo.
    basic_fields = CardSummaryResponse.model_validate(card).model_dump()
    return CardDetailResponse(
        **basic_fields,
        color=card.color,
        attribute=card.attribute,
        affiliation_text=card.affiliation_text,
        effect_text=card.effect_text,
        colors=sorted(c.name for c in card.colors),
        attributes=sorted(a.name for a in card.attributes),
        archetypes=sorted(a.name for a in card.archetypes),
        keywords=sorted(k.name for k in card.keywords),
        printings=[
            CardPrintingResponse.model_validate(p)
            for p in sorted(
                card.printings,
                key=lambda p: (p.product_set_id, p.variant_code, p.id),
            )
        ],
    )


# Fiksne domene čuvamo kao izbor i dok je katalog prazan. Ostale domene
# (archetypes, sets, cost, power, ...) učitavamo iz stvarne baze.
_CARD_TYPES = ("Leader", "Character", "Event", "Stage", "DON!!")
_RARITIES = ("C", "UC", "R", "SR", "SEC", "L", "SP", "TR", "Promo", "DON!!")
_BLOCK_ICONS = ("1", "2", "3", "4", "5", "X")
_COLORS = ("Red", "Green", "Blue", "Purple", "Black", "Yellow")
_ATTRIBUTES = ("Slash", "Strike", "Ranged", "Special", "Wisdom", "?")


def _preferred_order(values: list[str], preferred: tuple[str, ...]) -> list[str]:
    """Poznate vrijednosti po željenom redoslijedu, nove vrijednosti na kraju."""
    available = set(values)
    return [v for v in preferred if v in available] + sorted(available - set(preferred))


def _with_defaults(values: list[str], defaults: tuple[str, ...]) -> list[str]:
    """Postojeće + službene osnovne opcije, bez duplikata."""
    return list(defaults) + sorted(set(values) - set(defaults))


async def get_card_filters(db: AsyncSession) -> CardFilterOptionsResponse:
    """Pripremi javne opcije; novo otkriveni podaci pojavljuju se automatski."""
    values = await card_repo.get_filter_values(db)
    counter_values = sorted(set(values["counter_values"]) | {1000, 2000})
    # None nije broj 0: znači da tiskani Counter ne postoji.
    return CardFilterOptionsResponse(
        colors=_preferred_order(values["colors"], _COLORS),
        card_types=_with_defaults(values["card_types"], _CARD_TYPES),
        costs=sorted(set(values["costs"])),
        powers=sorted(set(values["powers"])),
        attributes=_preferred_order(values["attributes"], _ATTRIBUTES),
        counter_values=[None, *counter_values],
        block_icons=_with_defaults(values["block_icons"], _BLOCK_ICONS),
        keywords=sorted(set(values["keywords"])),
        archetypes=sorted(set(values["archetypes"])),
        sets=[CardSetFilterOption.model_validate(s) for s in values["sets"]],
        rarities=_with_defaults(values["rarities"], _RARITIES),
        variants=_with_defaults(values["variants"], ("regular",)),
    )
