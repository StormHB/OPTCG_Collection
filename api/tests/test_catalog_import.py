"""Testovi uvoza bez PostgreSQL-a i bez pristupnih podataka."""
import asyncio
import csv
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.import_catalog import CatalogImportError, CatalogRow, import_rows, read_catalog_csv
from app.models import Base, Card, CardPrinting, CardSet, Color


class DbBridge:
    def __init__(self, session):
        self.session = session

    async def scalars(self, statement):
        return self.session.scalars(statement)

    def add(self, obj):
        self.session.add(obj)


def make_csv(tmp_path: Path, rows):
    path = tmp_path / "catalog.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["set_code", "card_code", "name", "color", "rarity", "image_url"])
        w.writerows(rows)
    return path


def test_validation_and_dual_color(tmp_path):
    f = make_csv(tmp_path, [
        ["OP01", "OP01-001", "Zoro", "Red/Green", "L", ""],
        ["PRB01", "OP01-001", "Zoro", "Red/Green", "L", ""],
    ])
    r = read_catalog_csv(f)
    assert len(r) == 2
    assert r[0].colors == ("Red", "Green")
    assert r[1].original_set_code == "OP01"


@pytest.mark.parametrize("bad_row", [
    ["OP01", "FAIL", "Zoro", "Red", "L", ""],
    ["OP01", "OP01-001", "", "Red", "L", ""],
    ["OP01", "OP01-001", "Zoro", "Pink", "L", ""],
    ["OP01", "OP01-001", "Zoro", "Red", "INVALID", ""],
    ["OP01", "OP01-001", "Zoro", "Red", "L", "http://unsafe.test/a.png"],
])
def test_validation_rejects_bad_rows(tmp_path, bad_row):
    with pytest.raises(CatalogImportError):
        read_catalog_csv(make_csv(tmp_path, [bad_row]))


def test_validation_rejects_duplicate_printing(tmp_path):
    row = ["OP01", "OP01-001", "Zoro", "Red", "L", ""]
    with pytest.raises(CatalogImportError, match="ponovljeno"):
        read_catalog_csv(make_csv(tmp_path, [row, row]))


def test_import_prb_and_idempotency_no_quantity_changes():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([
            CardSet(code="OP01", name="OP01", sort_order=1),
            CardSet(code="PRB01", name="PRB01", sort_order=2),
            Color(name="Red"), Color(name="Green"),
        ])
        s.commit()
        rows = [
            CatalogRow("OP01", "OP01-001", "Zoro", ("Red", "Green"), "L", "https://example.com/a.png"),
            CatalogRow("PRB01", "OP01-001", "Zoro", ("Red", "Green"), "L", "https://example.com/b.png"),
        ]
        first = asyncio.run(import_rows(DbBridge(s), rows))
        s.commit()
        assert (first.new_cards, first.new_printings, first.new_color_links) == (1, 2, 2)
        cards = s.scalars(select(Card)).all()
        assert len(cards) == 1
        assert cards[0].card_type == "Leader"
        assert len(cards[0].colors) == 2
        assert len(s.scalars(select(CardPrinting)).all()) == 2
        second = asyncio.run(import_rows(DbBridge(s), rows))
        s.commit()
        assert (second.new_cards, second.new_printings, second.new_color_links) == (0, 0, 0)
        assert len(s.scalars(select(CardPrinting)).all()) == 2
    engine.dispose()


def test_missing_seed_values_does_not_import():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        with pytest.raises(CatalogImportError, match="seed"):
            asyncio.run(import_rows(DbBridge(s), [CatalogRow("OP01", "OP01-001", "Zoro", ("Red",), "L", None)]))
        assert s.scalars(select(Card)).all() == []
    engine.dispose()
