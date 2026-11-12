"""Siguran lokalni uvoz osnovnog kataloga iz CSV-a nastalog iz našeg Excela.

Pokretanje unutar api/: python -m app.import_catalog --file ../data/catalog_from_excel.csv
Primjena: python -m app.import_catalog --file ../data/catalog_from_excel.csv --apply

Namjerno NE uvozi korisničke količine, napomene, DON!! ni neprovjerene OP18 podatke.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Card, CardPrinting, CardSet, Color

EXPECTED_COLUMNS = ("set_code", "card_code", "name", "color", "rarity", "image_url")
CARD_CODE_PATTERN = re.compile(r"^(?:(?:OP|EB|ST|PRB)\d{2}|P)-\d{3}$")
COLOR_NAMES = {"Red", "Green", "Blue", "Purple", "Black", "Yellow"}
RARITIES = {"C", "UC", "R", "SR", "SEC", "L", "P", "Promo"}
SET_PATTERN = re.compile(r"^(?:(?:OP|EB|ST|PRB)\d{2}|P)$")


class CatalogImportError(ValueError):
    """Neispravan unos: radije prekinuti nego tiho kvariti katalog."""


@dataclass(frozen=True)
class CatalogRow:
    set_code: str  # U kojem sheetu / proizvodu se fizičko izdanje pojavljuje.
    card_code: str  # Izvorni broj karte, npr. OP01-001 i u PRB01 reprintu.
    name: str
    colors: tuple[str, ...]
    rarity: str
    image_url: str | None

    @property
    def original_set_code(self) -> str:
        return self.card_code.split("-", 1)[0]


def read_catalog_csv(path: Path) -> list[CatalogRow]:
    """Pročitaj i VALIDIRAJ sve retke prije prve operacije nad bazom."""
    if not path.is_file():
        raise CatalogImportError(f"Ne postoji datoteka: {path}")
    rows: list[CatalogRow] = []
    seen_printings: set[tuple[str, str]] = set()
    card_names: dict[str, str] = {}
    card_colors: dict[str, tuple[str, ...]] = {}

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != EXPECTED_COLUMNS:
            raise CatalogImportError(
                f"CSV zaglavlje mora biti: {', '.join(EXPECTED_COLUMNS)}"
            )
        for line_number, data in enumerate(reader, start=2):
            if not any(value and value.strip() for value in data.values() if isinstance(value, str)):
                continue
            if None in data:
                raise CatalogImportError(f"Red {line_number}: neočekivani dodatni stupci")
            set_code = (data["set_code"] or "").strip().upper()
            code = (data["card_code"] or "").strip().upper()
            name = (data["name"] or "").strip()
            rarity = (data["rarity"] or "").strip()
            color_string = (data["color"] or "").strip()
            image_url = (data["image_url"] or "").strip() or None
            if not SET_PATTERN.fullmatch(set_code):
                raise CatalogImportError(f"Red {line_number}: nepoznata oznaka seta {set_code!r}")
            if not CARD_CODE_PATTERN.fullmatch(code):
                raise CatalogImportError(f"Red {line_number}: neispravan broj karte {code!r}")
            if not name or len(name) > 160:
                raise CatalogImportError(f"Red {line_number}: neispravan naziv karte")
            if rarity not in RARITIES:
                raise CatalogImportError(f"Red {line_number}: nepoznata rijetkost {rarity!r}")
            if image_url:
                url = urlsplit(image_url)
                if url.scheme != "https" or not url.netloc or len(image_url) > 600:
                    raise CatalogImportError(f"Red {line_number}: slika mora biti HTTPS URL")
            colors = tuple(dict.fromkeys(p.strip().title() for p in color_string.split("/") if p.strip()))
            if not colors or set(colors) - COLOR_NAMES:
                raise CatalogImportError(f"Red {line_number}: neispravne boje {color_string!r}")
            key = (set_code, code)
            if key in seen_printings:
                raise CatalogImportError(f"Red {line_number}: ponovljeno izdanje {key}")
            seen_printings.add(key)
            if code in card_names and card_names[code] != name:
                raise CatalogImportError(f"Red {line_number}: različita imena za {code}")
            if code in card_colors and set(card_colors[code]) != set(colors):
                raise CatalogImportError(f"Red {line_number}: različite boje za {code}")
            card_names[code] = name
            card_colors[code] = colors
            rows.append(CatalogRow(set_code, code, name, colors, rarity, image_url))

    if not rows:
        raise CatalogImportError("CSV nema valjanih zapisa")
    return rows


@dataclass
class ImportResult:
    new_cards: int = 0
    new_printings: int = 0
    new_color_links: int = 0
    filled_images: int = 0
    filled_rarities: int = 0


async def import_rows(db, rows: list[CatalogRow]) -> ImportResult:
    """Idempotentan upsert; vanjske količine i postojeće vrijednosti NE mijenjamo.

    Transakciju i commit/rollback kontrolira pozivatelj.
    """
    sets = {s.code: s for s in (await db.scalars(select(CardSet))).all()}
    colors = {c.name: c for c in (await db.scalars(select(Color))).all()}
    needed_sets = {r.set_code for r in rows} | {r.original_set_code for r in rows}
    missing_sets = needed_sets - sets.keys()
    missing_colors = {c for r in rows for c in r.colors} - colors.keys()
    if missing_sets or missing_colors:
        raise CatalogImportError(
            f"Nedostaju seed vrijednosti; setovi={sorted(missing_sets)}, boje={sorted(missing_colors)}. "
            "Pokreni prvo python -m app.seed"
        )

    cards = {
        c.code: c
        for c in (await db.scalars(select(Card).options(selectinload(Card.colors)))).all()
    }
    set_by_id = {s.id: s.code for s in sets.values()}
    card_by_id = {c.id: c.code for c in cards.values()}
    printings = {}
    for p in (await db.scalars(select(CardPrinting))).all():
        # Za stari sadržaj koji nije regular ne diramo varijante.
        if p.variant_code == "regular" and p.card_id in card_by_id:
            printings[(set_by_id[p.product_set_id], card_by_id[p.card_id])] = p

    result = ImportResult()
    for row in rows:
        card = cards.get(row.card_code)
        if card is None:
            card = Card(
                code=row.card_code,
                name=row.name,
                original_set=sets[row.original_set_code],
                color="/".join(row.colors),
                card_type="Leader" if row.rarity == "L" else None,
                colors=[colors[c] for c in row.colors],
            )
            db.add(card)
            cards[row.card_code] = card
            result.new_cards += 1
            result.new_color_links += len(row.colors)
        else:
            if card.name != row.name or (
                card.original_set_id is not None
                and card.original_set_id != sets[row.original_set_code].id
            ):
                raise CatalogImportError(f"Sukob s postojećom kartom {row.card_code} — uvoz prekinut")
            existing = {c.name for c in card.colors}
            for name in row.colors:
                if name not in existing:
                    card.colors.append(colors[name])
                    result.new_color_links += 1

        key = (row.set_code, row.card_code)
        printing = printings.get(key)
        # Promotivnu rijetkost prikazujemo pod stabilnom kategorijom Promo.
        rarity = "Promo" if row.rarity == "P" else row.rarity
        if printing is None:
            printing = CardPrinting(
                card=card,
                product_set=sets[row.set_code],
                variant_code="regular",
                rarity=rarity,
                image_url=row.image_url,
            )
            db.add(printing)
            printings[key] = printing
            result.new_printings += 1
        else:
            if printing.rarity is None:
                printing.rarity = rarity
                result.filled_rarities += 1
            if printing.image_url is None and row.image_url:
                printing.image_url = row.image_url
                result.filled_images += 1
    return result


async def _run(path: Path, apply: bool) -> None:
    rows = read_catalog_csv(path)
    by_set = Counter(r.set_code for r in rows)
    unique_cards = len({r.card_code for r in rows})
    print(f"CSV: {len(rows)} izdanja, {unique_cards} jedinstvenih karata, {len(by_set)} sheetova/setova")
    print(f"Npr. OP01={by_set.get('OP01', 0)}, PRB01={by_set.get('PRB01', 0)}, PRB02={by_set.get('PRB02', 0)}")
    if not apply:
        print("SUHI POKUS: baza nije promijenjena. Za stvarni uvoz dodaj --apply.")
        return
    from app.core.database import AsyncSessionLocal

    # Ako se bilo što sruši, session.begin() radi automatski ROLLBACK.
    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await import_rows(db, rows)
    print(
        "UVOZ USPJEŠAN: novih karata={new_cards}, novih izdanja={new_printings}, "
        "novih veza s bojama={new_color_links}, dopunjenih slika={filled_images}, "
        "dopunjenih rijetkosti={filled_rarities}".format(**vars(result))
    )
    print("Korisničke količine i napomene NISU mijenjane.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import kataloga iz Excel-izvedenog CSV-a")
    parser.add_argument("--file", type=Path, required=True, help="putanja CSV datoteke")
    parser.add_argument("--apply", action="store_true", help="primijeni sve promjene u jednoj DB transakciji")
    args = parser.parse_args()
    try:
        asyncio.run(_run(args.file, args.apply))
    except (CatalogImportError, OSError) as exc:
        parser.exit(1, f"GREŠKA: {exc}\n")


if __name__ == "__main__":
    main()
