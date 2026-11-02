"""Provjere definicija ORM modela bez spajanja na bazu."""

from app.models import Base


def test_required_tables_exist() -> None:
    assert set(Base.metadata.tables) == {
        "users", "card_sets", "cards", "card_printings", "collection_entries"
    }


def test_collection_constraints_exist() -> None:
    table = Base.metadata.tables["collection_entries"]
    names = {c.name for c in table.constraints}
    assert "uq_user_printing" in names
    assert "ck_collection_quantity_nonnegative" in names
