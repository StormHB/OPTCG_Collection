"""Pydantic sheme javnog kataloga karata."""

from pydantic import BaseModel, ConfigDict, Field


class CardSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    original_set_id: int
    card_type: str | None = None
    cost: int | None = None
    power: int | None = None
    counter: int | None = None
    life: int | None = None


class CardPageResponse(BaseModel):
    items: list[CardSummaryResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class CardPrintingResponse(BaseModel):
    """Jedna fizička verzija karte (regular, alt, manga ili reprint)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_set_id: int
    variant_code: str
    rarity: str | None = None
    image_url: str | None = None
    block_icon: str | None = None


class CardDetailResponse(CardSummaryResponse):
    """Detalji osnovne karte sa svim pripadnostima i izdanjima."""
    color: str | None = None  # Privremeni tekstualni stupac; stari uvozi.
    attribute: str | None = None
    affiliation_text: str | None = None
    effect_text: str | None = None
    colors: list[str]
    attributes: list[str]
    archetypes: list[str]
    keywords: list[str]
    printings: list[CardPrintingResponse]


class CardSetFilterOption(BaseModel):
    """Set može biti izvorni set karte ili set u kojem se nalazi reprint."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class CardFilterOptionsResponse(BaseModel):
    """Opcije za Vue dropdownove, bez korisničkih podataka."""
    colors: list[str]
    card_types: list[str]
    costs: list[int]
    powers: list[int]
    attributes: list[str]
    counter_values: list[int | None]  # NULL = nema tiskane Counter vrijednosti.
    block_icons: list[str]
    keywords: list[str]
    archetypes: list[str]
    sets: list[CardSetFilterOption]
    rarities: list[str]
    variants: list[str]  # Sirovi variant_code, normalizacija u kasnijem koraku.
