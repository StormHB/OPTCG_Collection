"""Korak 9B: validacija posudbi i vraćanja (vremenska zona obavezna)."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class CardLoanCreate(BaseModel):
    printing_id: int = Field(ge=1)
    direction: Literal["lent", "borrowed"]
    person_name: str = Field(min_length=1, max_length=160)
    quantity: int = Field(ge=1, le=999_999)
    loaned_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("person_name")
    @classmethod
    def person_cannot_be_blank(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Ime osobe ne smije biti prazno")
        return name


class CardLoanReturn(BaseModel):
    quantity: int = Field(ge=1, le=999_999)
    returned_at: AwareDatetime | None = None


class CardLoanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    printing_id: int
    direction: Literal["lent", "borrowed"]
    person_name: str
    quantity: int
    quantity_returned: int
    outstanding_quantity: int
    loaned_at: AwareDatetime
    due_at: AwareDatetime | None
    returned_at: AwareDatetime | None
    note: str | None
    # Točan printing; pogodno za kompaktni Vue popis i hover pregled slike.
    card_code: str
    card_name: str
    set_code: str
    variant_code: str
    image_url: str | None
