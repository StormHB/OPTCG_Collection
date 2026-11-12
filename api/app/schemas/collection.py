"""Pydantic sheme za osobnu kolekciju (čitanje, unos i izmjene)."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CollectionEntryResponse(BaseModel):
    """Postojeći oblik odgovora ostaje kompatibilan s predavanjem 4."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    printing_id: int
    quantity: int
    note: str | None = None


class CollectionEntryCreate(BaseModel):
    """Za novu stavku navodimo točno fizičko izdanje i njegovu količinu."""

    printing_id: int = Field(ge=1)
    quantity: int = Field(ge=0, le=999_999)
    note: str | None = Field(default=None, max_length=1000)


class CollectionEntryUpdate(BaseModel):
    """PATCH ažurira samo navedena polja. note=null briše napomenu."""

    quantity: int | None = Field(default=None, ge=0, le=999_999)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_changes(self) -> "CollectionEntryUpdate":
        if not self.model_fields_set:
            raise ValueError("Potrebno je poslati quantity ili note")
        if "quantity" in self.model_fields_set and self.quantity is None:
            raise ValueError("quantity ne moze biti null")
        return self
