"""Javne HTTP rute za katalog karata (predavanje 5)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query
from pydantic import AfterValidator, Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.errors import AppError
from app.core.optional_auth import get_collection_filter_user
from app.models.user import User
from app.schemas.card import (
    CardDetailResponse,
    CardFilterOptionsResponse,
    CardPageResponse,
)
from app.schemas.card_search import CardSearchFilters
from app.services import card_service

router = APIRouter()

# Zasad podržani rasponi TCG filtera. Izvan raspona vracamo 422 prije SQL-a.
CostSelection = Annotated[int, Field(ge=0, le=10)]
PowerSelection = Annotated[int, Field(ge=0, le=13_000)]


def _validate_counter_value(value: str) -> str:
    """Izbjegni goleme brojeve i vrijednosti izvan PostgreSQL integer raspona."""
    if value.lower() != "none" and int(value) > 2_147_483_647:
        raise ValueError("Counter vrijednost prelazi podrzani raspon")
    return value


# 'none' predstavlja SQL NULL (a nije 0). Prvo provjera duljine i regexa,
# tek nakon toga pretvaranje u int nad maksimalno 10 znakova.
CounterSelection = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=10,
        pattern=r"^(?:[Nn][Oo][Nn][Ee]|0|[1-9][0-9]*)$",
    ),
    AfterValidator(_validate_counter_value),
]


@router.get("", response_model=CardPageResponse)
async def list_cards(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    colors: list[str] | None = Query(default=None),
    card_types: list[str] | None = Query(default=None),
    costs: list[CostSelection] | None = Query(default=None),
    powers: list[PowerSelection] | None = Query(default=None),
    attributes: list[str] | None = Query(default=None),
    counter_values: list[CounterSelection] | None = Query(default=None),
    block_icons: list[str] | None = Query(default=None),
    keywords: list[str] | None = Query(default=None),
    archetypes: list[str] | None = Query(default=None),
    sets: list[str] | None = Query(default=None),
    rarities: list[str] | None = Query(default=None),
    variants: list[str] | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    collection_status: list[Literal["owned", "missing", "playset"]] | None = Query(
        default=None,
        description=(
            "Privatni filter: owned, missing ili playset. Ponovi parametar "
            "za OR (npr. collection_status=owned&collection_status=playset). "
            "Zahtijeva JWT access token; koristi isključivo prijavljenog korisnika."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_collection_filter_user),
) -> CardPageResponse:
    """Ponovljeni parametri = OR, različite kategorije = AND.

    Npr. /cards?colors=Red&colors=Yellow&costs=1&costs=2&powers=6000
    Counter vrijednost bez tiskane oznake: counter_values=none.
    """
    if collection_status and current_user is None:
        raise AppError(
            "invalid_credentials",
            "Za osobne filtere potreban je access token",
            401,
        )

    filters = CardSearchFilters(
        colors=tuple(colors or ()),
        card_types=tuple(card_types or ()),
        costs=tuple(costs or ()),
        powers=tuple(powers or ()),
        attributes=tuple(attributes or ()),
        counter_values=tuple(counter_values or ()),
        block_icons=tuple(block_icons or ()),
        keywords=tuple(keywords or ()),
        archetypes=tuple(archetypes or ()),
        sets=tuple(sets or ()),
        rarities=tuple(rarities or ()),
        variants=tuple(variants or ()),
        search=search,
        collection_statuses=tuple(collection_status or ()),
        collection_user_id=current_user.id if collection_status else None,
    )
    return await card_service.get_cards(db, limit=limit, offset=offset, filters=filters)


@router.get("/filters", response_model=CardFilterOptionsResponse)
async def list_card_filters(
    db: AsyncSession = Depends(get_db),
) -> CardFilterOptionsResponse:
    """Dostupne opcije za filtere; mora stajati prije /{card_id}."""
    return await card_service.get_card_filters(db)


@router.get("/{card_id}", response_model=CardDetailResponse)
async def read_card(
    card_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
) -> CardDetailResponse:
    """Javni detalji jedne karte sa svim dostupnim izdanjima."""
    return await card_service.get_card_detail(db, card_id=card_id)
