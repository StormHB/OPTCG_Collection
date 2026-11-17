"""Korak 9B: validacija posudbi i vraćanja (vremenska zona obavezna)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
)


def _date_from_iso_string_or_datetime(value: object) -> object:
    """JSON datum mora biti string; Python datetime je dopušten za interni kod."""
    if not isinstance(value, (str, datetime)):
        raise ValueError("Datum mora biti ISO 8601 tekst s vremenskom zonom")
    return value


LoanDate = Annotated[
    AwareDatetime,
    BeforeValidator(_date_from_iso_string_or_datetime),
    Field(description="ISO 8601 datum i vrijeme s obaveznom vremenskom zonom."),
]


class CardLoanCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "printing_id": 13,
                "direction": "lent",
                "person_name": "Ivan",
                "quantity": 2,
                "loaned_at": "2026-11-10T13:00:00+01:00",
                "due_at": "2026-11-17T12:00:00Z",
                "note": "Posudeno za turnir",
            }
        },
    )

    printing_id: int = Field(strict=True, ge=1)
    direction: Literal["lent", "borrowed"]
    person_name: str = Field(strict=True, min_length=1, max_length=160)
    quantity: int = Field(strict=True, ge=1, le=999_999)
    loaned_at: LoanDate | None = None
    due_at: LoanDate | None = None
    note: str | None = Field(default=None, strict=True, max_length=1000)

    @field_validator("person_name")
    @classmethod
    def person_cannot_be_blank(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Ime osobe ne smije biti prazno")
        return name

    @field_validator("note")
    @classmethod
    def note_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Napomena ne smije biti prazna; koristi null za izostanak")
        return value


class CardLoanReturn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "quantity": 1,
                "returned_at": "2026-11-12T13:00:00+01:00",
            }
        },
    )

    quantity: int = Field(strict=True, ge=1, le=999_999)
    returned_at: LoanDate | None = None


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
