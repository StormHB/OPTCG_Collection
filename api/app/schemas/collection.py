"""Pydantic sheme za osobnu kolekciju (čitanje, unos i izmjene)."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CollectionEntryResponse(BaseModel):
    """Postojeći oblik odgovora ostaje kompatibilan s predavanjem 4."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    printing_id: int
    quantity: int
    note: str | None = None


class CollectionEntryCreate(BaseModel):
    """Za novu stavku navodimo točno fizičko izdanje i njegovu količinu."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"printing_id": 13, "quantity": 4, "note": "Za deck"}
        },
    )

    printing_id: int = Field(strict=True, ge=1)
    quantity: int = Field(strict=True, ge=0, le=999_999)
    note: str | None = Field(default=None, strict=True, max_length=1000)

    @field_validator("note")
    @classmethod
    def note_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Napomena ne smije biti prazna; koristi null za brisanje")
        return value


class CollectionEntryUpdate(BaseModel):
    """PATCH ažurira samo navedena polja. note=null briše napomenu."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"quantity": 4, "note": None}},
    )

    quantity: int | None = Field(default=None, strict=True, ge=0, le=999_999)
    note: str | None = Field(default=None, strict=True, max_length=1000)

    @field_validator("note")
    @classmethod
    def note_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Napomena ne smije biti prazna; koristi null za brisanje")
        return value

    @model_validator(mode="after")
    def validate_changes(self) -> "CollectionEntryUpdate":
        if not self.model_fields_set:
            raise ValueError("Potrebno je poslati quantity ili note")
        if "quantity" in self.model_fields_set and self.quantity is None:
            raise ValueError("quantity ne moze biti null")
        return self
