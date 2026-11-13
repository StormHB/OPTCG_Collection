"""Korak 10A: zbroj osobnih količina i dovršenih playsetova."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories import collection_stats_repo
from app.schemas.collection_stats import CollectionStatsResponse, PlaysetBreakdown
from app.services.collection_service import ensure_collection_owner
from app.services.playset_service import playset_category, playset_threshold


async def get_collection_stats(
    db: AsyncSession, current_user: User, owner_user_id: int
) -> CollectionStatsResponse:
    """Autoriziraj PRIJE upita; ne koristi broj posuđenih karata."""
    ensure_collection_owner(current_user, owner_user_id)
    rows = await collection_stats_repo.load_owned_printings(db, owner_user_id)

    total_cards = 0
    playsets_by_type = {"leader": 0, "don": 0, "other": 0}
    for quantity, card_type, rarity, set_code, card_code in rows:
        total_cards += quantity
        category = playset_category(
            card_type, rarity=rarity, set_code=set_code, card_code=card_code
        )
        threshold = playset_threshold(
            card_type, rarity=rarity, set_code=set_code, card_code=card_code
        )
        if quantity >= threshold:
            playsets_by_type[category] += 1

    return CollectionStatsResponse(
        user_id=owner_user_id,
        total_cards=total_cards,
        distinct_printings=len(rows),
        playsets=sum(playsets_by_type.values()),
        playsets_by_type=PlaysetBreakdown(**playsets_by_type),
    )
