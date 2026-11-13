"""Odabrani filteri za javni katalog (nezavisno od HTTP sloja)."""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CardSearchFilters:
    """Više vrijednosti u jednoj kategoriji = OR; kategorije međusobno = AND."""

    colors: tuple[str, ...] = ()
    card_types: tuple[str, ...] = ()
    costs: tuple[int, ...] = ()
    powers: tuple[int, ...] = ()
    attributes: tuple[str, ...] = ()
    counter_values: tuple[str, ...] = ()  # "none" ili cijeli broj, npr. "1000"
    block_icons: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    archetypes: tuple[str, ...] = ()
    sets: tuple[str, ...] = ()  # Kod proizvoda/izdanja: "OP01", "PRB01", "DON".
    rarities: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()  # Izvorni variant_code, npr. "regular", "alt".
    search: str | None = None
    # Korak 10B: statusi su OR unutar kategorije; korisnik dolazi samo iz JWT-a.
    collection_statuses: tuple[str, ...] = ()
    collection_user_id: int | None = None

    def is_active(self) -> bool:
        """Ne mijenjamo ponašanje i mockove starog GET /cards bez filtera."""
        return any(
            (
                self.colors,
                self.card_types,
                self.costs,
                self.powers,
                self.attributes,
                self.counter_values,
                self.block_icons,
                self.keywords,
                self.archetypes,
                self.sets,
                self.rarities,
                self.variants,
                self.search and self.search.strip(),
                self.collection_statuses,
            )
        )
