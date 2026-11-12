from app.seed import ATTRIBUTES, COLORS, initial_sets
from app.services.playset_service import is_playset


def test_seed_includes_don_once() -> None:
    codes = [code for code, _ in initial_sets()]
    assert len(codes) == 64
    assert codes.count("DON") == 1
    assert len(codes) == len(set(codes))


def test_controlled_values_are_unique() -> None:
    assert len(COLORS) == 6 and len(set(COLORS)) == 6
    assert len(ATTRIBUTES) == 6 and len(set(ATTRIBUTES)) == 6


def test_playset_rules() -> None:
    assert is_playset("Leader", 1)
    assert not is_playset("Leader", 0)
    assert not is_playset("Character", 3)
    assert is_playset("Character", 4)
    assert not is_playset("DON!!", 9)
    assert is_playset("DON!!", 10)
    assert not is_playset("Event", 0)
