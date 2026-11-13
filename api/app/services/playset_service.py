"""Pravila playsetova za osobnu kolekciju (ne mijenjaju stvarnu količinu)."""

from typing import Literal

PlaysetCategory = Literal["leader", "don", "other"]


def playset_category(
    card_type: str | None,
    *,
    rarity: str | None = None,
    set_code: str | None = None,
    card_code: str | None = None,
) -> PlaysetCategory:
    """Fallback na rarity/set/kod za nedovoljno popunjene kataloge.

    Leader: tip Leader ili tiskana rijetkost L/Leader.
    DON!!: tip DON, kod DON-... ili set DON.
    Sve ostalo: obična karta (4 primjerka).
    """
    kind = (card_type or "").strip().casefold()
    rare = (rarity or "").strip().casefold()
    product = (set_code or "").strip().casefold()
    code = (card_code or "").strip().casefold()

    if kind == "leader" or rare in {"l", "leader"}:
        return "leader"
    if (
        kind in {"don", "don!!", "don!!!"}
        or rare in {"don", "don!!", "don!!!"}
        or product == "don"
        or code.startswith("don-")
    ):
        return "don"
    return "other"


def playset_threshold(
    card_type: str | None,
    *,
    rarity: str | None = None,
    set_code: str | None = None,
    card_code: str | None = None,
) -> int:
    """Jedan dovršen playset po izdanju kad se dosegne propisani prag."""
    category = playset_category(
        card_type, rarity=rarity, set_code=set_code, card_code=card_code
    )
    return {"leader": 1, "don": 10, "other": 4}[category]


def is_playset(card_type: str, quantity: int) -> bool:
    """Zadržana stara signatura kako postojeći testovi ostaju kompatibilni."""
    return quantity >= playset_threshold(card_type)
