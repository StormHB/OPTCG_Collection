"""Read-only rezultat za GET /collections/{user_id}/stats."""

from pydantic import BaseModel, Field


class PlaysetBreakdown(BaseModel):
    leader: int = Field(ge=0)
    don: int = Field(ge=0)
    other: int = Field(ge=0)


class CollectionStatsResponse(BaseModel):
    user_id: int = Field(ge=1)
    total_cards: int = Field(ge=0)
    distinct_printings: int = Field(ge=0)
    playsets: int = Field(ge=0)
    playsets_by_type: PlaysetBreakdown
