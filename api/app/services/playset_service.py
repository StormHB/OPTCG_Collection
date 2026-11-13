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


def playset_threshold_sql(card_type, *, rarity, set_code, card_code):
    """SQL pandan playset_threshold() za filtriranje bez učitavanja cijelog kataloga.

    Oba izračuna moraju slijediti iste pragove i fallback redoslijed.
    Izrazi su SQLAlchemy stupci, kompatibilni s PostgreSQL-om i SQLiteom.
    """
    from sqlalchemy import case, func, or_

    def normalize(value):
        return func.lower(func.trim(func.coalesce(value, "")))

    kind = normalize(card_type)
    rare = normalize(rarity)
    product = normalize(set_code)
    code = normalize(card_code)
    is_leader = or_(kind == "leader", rare.in_(("l", "leader")))
    is_don = or_(
        kind.in_(("don", "don!!", "don!!!")),
        rare.in_(("don", "don!!", "don!!!")),
        product == "don",
        code.like("don-%"),
    )
    return case((is_leader, 1), (is_don, 10), else_=4)
