"""Pragovi dovrsenosti kolekcije (nas dogovor, ne sluzbeni DON!! playset)."""


def is_playset(card_type: str, quantity: int) -> bool:
    kind = card_type.strip().lower()
    if kind == "leader":
        return quantity >= 1
    if kind in {"don!!", "don", "don!!!"}:
        return quantity >= 10
    return quantity >= 4
