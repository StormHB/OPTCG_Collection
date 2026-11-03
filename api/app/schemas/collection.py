"""Javni oblik zapisa kolekcije; ne otkriva podatke drugih korisnika."""

from pydantic import BaseModel, ConfigDict


class CollectionEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    printing_id: int
    quantity: int
    note: str | None = None
