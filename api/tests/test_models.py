"""Provjera strukture ORM metapodataka bez spajanja na produkcijsku bazu."""
from app.models import Base


def test_required_tables_exist() -> None:
    expected = {
        "users", "card_sets", "cards", "card_printings", "collection_entries",
        "colors", "attributes", "archetypes", "keywords",
        "card_colors", "card_attributes", "card_archetypes", "card_keywords",
        "printing_external_ids",
    }
    assert set(Base.metadata.tables) == expected


def test_collection_constraints_exist() -> None:
    table = Base.metadata.tables["collection_entries"]
    names = {constraint.name for constraint in table.constraints}
    assert "uq_user_printing" in names
    assert "ck_collection_quantity_nonnegative" in names


def test_external_ids_do_not_collide() -> None:
    table = Base.metadata.tables["printing_external_ids"]
    names = {constraint.name for constraint in table.constraints}
    assert "uq_printing_external_source_identity" in names


def test_association_tables_have_composite_primary_keys() -> None:
    pairs = {
        "card_colors": {"card_id", "color_id"},
        "card_attributes": {"card_id", "attribute_id"},
        "card_archetypes": {"card_id", "archetype_id"},
        "card_keywords": {"card_id", "keyword_id"},
    }
    for table_name, expected in pairs.items():
        table = Base.metadata.tables[table_name]
        assert {column.name for column in table.primary_key.columns} == expected
