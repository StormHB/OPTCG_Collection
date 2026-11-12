"""Korak 7: sigurna dopuna POSTOJEĆIH karata iz Koala Kollect JSONL baze.

Izvor: https://github.com/hotavocado/koala-kollect-data (CC BY 4.0 za
strukturu i podatke repozitorija, ali ne i za Bandai kartični tekst/slike).

Komande, pokretati iz api/:
  python -m app.enrich_catalog --download
  python -m app.enrich_catalog
  python -m app.enrich_catalog --apply

Namjerno ne stvara nove karte ili izdanja, ne mijenja korisničke kolekcije,
ne prepisuje postojeće vrijednosti i nikad ne preuzima slike na naš server.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Archetype, Attribute, Card, Color, Keyword
from app.seed import KEYWORDS

SOURCE_ROOTS = (
    "https://raw.githubusercontent.com/hotavocado/koala-kollect-data/main/",
    "https://cdn.jsdelivr.net/gh/hotavocado/koala-kollect-data@main/",
)
SOURCE_FILES = (
    "data/cards.jsonl",
    "data/card_observations/en.jsonl",
    "data/printings/en.jsonl",
)
DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "koala_snapshot"
CODE = re.compile(r"^(?:(?:OP|EB|ST|PRB)\d{2}|P)-\d{3}$", re.I)
VALID_TYPES = {"leader": "Leader", "character": "Character", "event": "Event", "stage": "Stage"}
VALID_COLORS = {"red", "green", "blue", "purple", "black", "yellow"}
VALID_ATTRIBUTES = {"slash", "strike", "ranged", "special", "wisdom", "?"}


class EnrichmentError(ValueError):
    """Izvorni podaci su neispravni ili nepotpuni; ništa ne upisivati."""


def _get_url_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "OPTCG-CollectionTracker/1.0"})
    with urlopen(request, timeout=45) as response:
        return response.read()


def _validate_file(raw: bytes, entry: dict, filename: str) -> None:
    actual_hash = hashlib.sha256(raw).hexdigest()
    expected_hash = entry.get("sha256")
    if not isinstance(expected_hash, str) or actual_hash != expected_hash:
        raise EnrichmentError(f"SHA-256 ne odgovara manifestu: {filename}")
    count = sum(bool(line.strip()) for line in raw.splitlines())
    if count != entry.get("rows"):
        raise EnrichmentError(
            f"Broj zapisa ne odgovara manifestu: {filename} "
            f"({count} umjesto {entry.get('rows')})"
        )


def download_snapshot(folder: Path, fetch=_get_url_bytes) -> str:
    """Preuzimanje i provjera u privremenom direktoriju, tek onda zamjena."""
    folder = folder.resolve()
    folder.parent.mkdir(parents=True, exist_ok=True)
    failures = []
    for root in SOURCE_ROOTS:
        tmp = Path(tempfile.mkdtemp(prefix="koala-stage-", dir=folder.parent))
        try:
            manifest_raw = fetch(root + "manifest.json")
            manifest = json.loads(manifest_raw)
            files_meta = manifest.get("files", {})
            if not isinstance(files_meta, dict):
                raise EnrichmentError("Manifest nema mapu files")
            (tmp / "manifest.json").write_bytes(manifest_raw)
            for name in SOURCE_FILES:
                if name not in files_meta:
                    raise EnrichmentError(f"Manifest ne sadrži {name}")
                content = fetch(root + name)
                _validate_file(content, files_meta[name], name)
                target = tmp / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            # Ne mijenjaj korisnikov postojeći snapshot ako preuzimanje nije valjano.
            if folder.exists():
                shutil.rmtree(folder)
            tmp.rename(folder)
            return str(manifest.get("generated_at", "datum nije naveden"))
        except (EnrichmentError, OSError, ValueError, UnicodeError) as exc:
            failures.append(f"{root}: {exc}")
        finally:
            if tmp.exists():
                shutil.rmtree(tmp)
    raise EnrichmentError("Preuzimanje nije uspjelo:\n" + "\n".join(failures))


def load_snapshot(folder: Path) -> tuple[dict[str, list[dict]], str]:
    path = folder / "manifest.json"
    if not path.is_file():
        raise EnrichmentError(f"Nedostaje {path}; prvo pokreni --download")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EnrichmentError(f"Nevaljan manifest: {exc}") from exc
    raw_rows: dict[str, list[dict]] = {}
    for name in SOURCE_FILES:
        file_path = folder / name
        try:
            content = file_path.read_bytes()
            _validate_file(content, manifest["files"][name], name)
            lines = [line for line in content.decode("utf-8-sig").splitlines() if line.strip()]
            rows = [json.loads(line) for line in lines]
            if not all(isinstance(row, dict) for row in rows):
                raise EnrichmentError(f"Nevaljan JSON objekt u {name}")
            raw_rows[name] = rows
        except (OSError, ValueError, KeyError, UnicodeError) as exc:
            raise EnrichmentError(f"Ne mogu učitati {name}: {exc}") from exc
    return raw_rows, str(manifest.get("generated_at", "nepoznato"))


def _values(value: object) -> tuple[str, ...]:
    """Koala čuva polja kao polja stringova. Za starije izvoze prihvaća se /."""
    if value is None:
        return ()
    if isinstance(value, str):
        candidates = value.split("/")
    elif isinstance(value, list) and all(isinstance(v, str) for v in value):
        candidates = [part for item in value for part in item.split("/")]
    else:
        raise EnrichmentError(f"Očekujem polje stringova, dobio {value!r}")
    return tuple(dict.fromkeys(v.strip() for v in candidates if v.strip()))


def _number(value: object, *, name: str, code: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise EnrichmentError(f"{code}: neispravan {name}: {value!r}")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and re.fullmatch(r"\+?[0-9]+", value.strip()):
        result = int(value.strip().removeprefix("+"))
    else:
        raise EnrichmentError(f"{code}: neispravan {name}: {value!r}")
    if result < 0 or result > 100000:
        raise EnrichmentError(f"{code}: {name} izvan dopuštenog raspona")
    return result


def _first(record: dict, fallback: dict, name: str) -> object:
    return record.get(name, fallback.get(name))


def _norm_block(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text not in {"1", "2", "3", "4", "5", "X"}:
        raise EnrichmentError(f"Nepoznata oznaka bloka: {value!r}")
    return text


def _image_key(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlsplit(url)
    return f"{parsed.netloc.lower()}{parsed.path.lower()}"


def recognize_keywords(effect: str, trigger: str) -> tuple[str, ...]:
    """Prepoznaje samo eksplicitne [oznake] + riječi K.O./Trash.

    '[Counter]' nije isto što i numerički Counter od +1000/+2000.
    """
    text = f"{effect}\n{trigger}"
    labels = [re.sub(r"\s+", " ", item.strip()).casefold() for item in re.findall(r"\[([^]]+)\]", text)]
    result = set()
    for name in KEYWORDS:
        low = name.casefold()
        if low == "don!! xn":
            if any(re.fullmatch(r"don!!\s*[x×]\s*\d+", label) for label in labels):
                result.add(name)
        elif low == "don!! -n":
            if any(re.fullmatch(r"don!!\s*[-−–]\s*\d+", label) for label in labels):
                result.add(name)
        elif low == "k.o.":
            if re.search(r"\bk\.o\.", text, flags=re.I):
                result.add(name)
        elif low == "trash":
            if re.search(r"\btrash\b", text, flags=re.I):
                result.add(name)
        elif low == "trigger":
            if trigger.strip() or low in labels:
                result.add(name)
        elif low in labels:
            result.add(name)
    return tuple(name for name in KEYWORDS if name in result)


@dataclass(frozen=True)
class EnrichmentRow:
    code: str
    name: str
    category: str | None
    cost: int | None
    power: int | None
    counter: int | None
    life: int | None
    colors: tuple[str, ...]
    attributes: tuple[str, ...]
    archetypes: tuple[str, ...]
    keywords: tuple[str, ...]
    effect_text: str | None
    base_image_url: str | None = None
    block_icon: str | None = None


def parse_enrichment(raw: dict[str, list[dict]]) -> tuple[list[EnrichmentRow], dict[str, int]]:
    cards = raw["data/cards.jsonl"]
    observations = raw["data/card_observations/en.jsonl"]
    printings = raw["data/printings/en.jsonl"]
    by_key: dict[str, dict] = {}
    by_number: set[str] = set()
    for item in cards:
        key, number = item.get("key"), item.get("number")
        if not isinstance(key, str) or not key:
            raise EnrichmentError("Card zapis nema key")
        if key in by_key:
            raise EnrichmentError(f"Duplicirani card key {key}")
        by_key[key] = item
        if isinstance(number, str) and CODE.fullmatch(number.upper()):
            if number.upper() in by_number:
                raise EnrichmentError(f"Duplicirani broj u Koala katalogu: {number}")
            by_number.add(number.upper())

    # Engleski opisi: ne uzimamo stare/superseded verzije nakon errate.
    current: dict[str, dict] = {}
    for obs in observations:
        if obs.get("superseded_at"):
            continue
        key = obs.get("card_key")
        if key not in by_key:
            raise EnrichmentError(f"EN observation za nepoznatu kartu: {key}")
        if key in current:
            raise EnrichmentError(f"Više aktivnih EN observation zapisa za {key}")
        current[key] = obs

    base_images: dict[str, list[dict]] = {}
    for printing in printings:
        if printing.get("variant") != "base":
            continue
        card_key = printing.get("card_key")
        if card_key in by_key:
            base_images.setdefault(card_key, []).append(printing)

    records: list[EnrichmentRow] = []
    stats = {"koala_cards": len(cards), "en_observations": len(current), "without_en": 0,
             "unnumbered_or_don": 0}
    for key, card in by_key.items():
        code = card.get("number")
        if not isinstance(code, str) or not CODE.fullmatch(code.upper()):
            stats["unnumbered_or_don"] += 1
            continue  # DON!! identitet se posebno obrađuje u sljedećem koraku.
        obs = current.get(key)
        if obs is None:
            stats["without_en"] += 1
            continue
        code = code.upper()
        name = obs.get("name") or card.get("name")
        if not isinstance(name, str) or not name.strip():
            raise EnrichmentError(f"{code}: nedostaje ime u izvornom katalogu")
        category_source = _first(obs, card, "category")
        category = None
        if category_source:
            category = VALID_TYPES.get(str(category_source).strip().casefold())
            if category is None:
                raise EnrichmentError(f"{code}: nepoznati tip {category_source!r}")
        colors = tuple(v.title() for v in _values(_first(obs, card, "colors")))
        if any(color.casefold() not in VALID_COLORS for color in colors):
            raise EnrichmentError(f"{code}: nepoznate boje {colors}")
        attributes = tuple("?" if v in {"?", "？"} else v.title()
                           for v in _values(_first(obs, card, "attributes")))
        if any(attr.casefold() not in VALID_ATTRIBUTES for attr in attributes):
            raise EnrichmentError(f"{code}: nepoznati atributi {attributes}")
        archetypes = _values(_first(obs, card, "types"))
        cost = _number(_first(obs, card, "cost"), name="cost", code=code)
        power = _number(_first(obs, card, "power"), name="power", code=code)
        counter = _number(_first(obs, card, "counter"), name="counter", code=code)
        life = _number(_first(obs, card, "life"), name="life", code=code)
        effect = str(obs.get("effect") or "").strip()
        trigger = str(obs.get("trigger") or "").strip()
        if trigger:
            # Izvor razlikuje effect i trigger; naša karta zasad ima samo effect_text.
            joined = f"{effect}\n[Trigger] {trigger}".strip()
        else:
            joined = effect
        keywords = recognize_keywords(effect, trigger)
        matched_base = base_images.get(key, [])
        base_image_url = block_icon = None
        if len(matched_base) == 1:
            base_image_url = matched_base[0].get("image_url")
            block_icon = _norm_block(matched_base[0].get("block_icon"))
        records.append(EnrichmentRow(
            code=code, name=name.strip(), category=category,
            cost=cost, power=power, counter=counter, life=life,
            colors=colors, attributes=attributes, archetypes=archetypes,
            keywords=keywords, effect_text=joined or None,
            base_image_url=base_image_url, block_icon=block_icon,
        ))
    return records, stats


@dataclass
class EnrichmentResult:
    matched: int = 0
    unmatched: int = 0
    cards_updated: int = 0
    fields_filled: int = 0
    relations_added: int = 0
    archetypes_created: int = 0
    block_icons_filled: int = 0
    conflicts: int = 0
    examples: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.conflicts += 1
        if len(self.examples) < 12:
            self.examples.append(message)


async def enrich_rows(db, rows: list[EnrichmentRow], *, apply: bool) -> EnrichmentResult:
    """Fill-only, ponovljiv postupak. `apply=False` je read-only DB pregled."""
    loaded = (await db.scalars(select(Card).options(
        selectinload(Card.colors), selectinload(Card.attributes),
        selectinload(Card.archetypes), selectinload(Card.keywords),
        selectinload(Card.printings),
    ))).all()
    cards_by_code = {card.code.upper(): card for card in loaded}
    colors = {c.name.casefold(): c for c in (await db.scalars(select(Color))).all()}
    attributes = {a.name.casefold(): a for a in (await db.scalars(select(Attribute))).all()}
    keywords = {k.name.casefold(): k for k in (await db.scalars(select(Keyword))).all()}
    archetypes = {a.name.casefold(): a for a in (await db.scalars(select(Archetype))).all()}
    unknown_archetypes: set[str] = set()
    result = EnrichmentResult()

    for row in rows:
        card = cards_by_code.get(row.code)
        if card is None:
            result.unmatched += 1
            continue
        result.matched += 1
        touched = False
        for attr, incoming in (
            ("card_type", row.category), ("cost", row.cost),
            ("power", row.power), ("counter", row.counter),
            ("life", row.life), ("effect_text", row.effect_text),
        ):
            if incoming is None:
                continue
            current = getattr(card, attr)
            if current is None or current == "":
                if apply:
                    setattr(card, attr, incoming)
                result.fields_filled += 1
                touched = True
            elif current != incoming:
                result.warn(f"{row.code} {attr}: baza={str(current)[:40]!r}, izvor={str(incoming)[:40]!r}")

        def link_values(field_name: str, incoming: tuple[str, ...], directory: dict, *, allow_new=False):
            nonlocal touched
            current_list = getattr(card, field_name)
            existing = {item.name.casefold() for item in current_list}
            if field_name == "colors" and existing and set(s.casefold() for s in incoming) != existing:
                if incoming:
                    result.warn(f"{row.code} colors: ne podudaraju se CSV i izvor")
                return
            for value in incoming:
                identity = value.casefold()
                if identity in existing:
                    continue
                obj = directory.get(identity)
                if obj is None and allow_new:
                    if identity not in unknown_archetypes:
                        result.archetypes_created += 1
                        unknown_archetypes.add(identity)
                    if apply:
                        obj = Archetype(name=value)
                        db.add(obj)
                        directory[identity] = obj
                if obj is None and not allow_new:
                    result.warn(f"{row.code} {field_name}: nedostaje seed {value!r}")
                    continue
                if apply:
                    current_list.append(obj)
                result.relations_added += 1
                touched = True
                existing.add(identity)

        link_values("colors", row.colors, colors)
        link_values("attributes", row.attributes, attributes)
        link_values("keywords", row.keywords, keywords)
        link_values("archetypes", row.archetypes, archetypes, allow_new=True)
        if row.attributes and (card.attribute is None or card.attribute == ""):
            if apply:
                card.attribute = "/".join(row.attributes)
            result.fields_filled += 1
            touched = True
        if row.archetypes and (card.affiliation_text is None or card.affiliation_text == ""):
            if apply:
                card.affiliation_text = "/".join(row.archetypes)
            result.fields_filled += 1
            touched = True

        # Block ikona pripada izdanju. Popunjavamo ISKLJUČIVO isto fizičko izdanje
        # čija se službena base ilustracija točno poklapa s postojećim URL-om.
        if row.block_icon is not None and row.base_image_url:
            source_image = _image_key(row.base_image_url)
            for printing in card.printings:
                if (printing.product_set_id == card.original_set_id
                        and printing.variant_code == "regular"
                        and _image_key(printing.image_url) == source_image):
                    if printing.block_icon is None:
                        if apply:
                            printing.block_icon = row.block_icon
                        result.block_icons_filled += 1
                        touched = True
                    elif printing.block_icon != row.block_icon:
                        result.warn(f"{row.code} block_icon: postojeće izdanje ima drukčiji blok")
        if touched:
            result.cards_updated += 1
    return result


async def _run(folder: Path, apply: bool) -> None:
    from app.core.database import AsyncSessionLocal

    source, date = load_snapshot(folder)
    rows, info = parse_enrichment(source)
    print(f"Koala snapshot: {date}")
    print(f"Izvor: {info['koala_cards']} karata; {info['en_observations']} aktivnih EN opisa")
    print(f"Obrada: {len(rows)} numeriranih EN karata; ",
          f"bez EN opisa={info['without_en']}; bez broja/DON={info['unnumbered_or_don']}")
    async with AsyncSessionLocal() as session:
        if apply:
            async with session.begin():
                result = await enrich_rows(session, rows, apply=True)
        else:
            result = await enrich_rows(session, rows, apply=False)
    print(
        f"Postojeće karte={result.matched}, bez lokalnog broja={result.unmatched}, "
        f"karte za dopunu={result.cards_updated}"
    )
    print(
        f"Polja za dopunu={result.fields_filled}, nove M:N veze={result.relations_added}, "
        f"novi archetypeovi={result.archetypes_created}, blok ikone={result.block_icons_filled}"
    )
    if result.conflicts:
        print(f"Upozorenja / neslaganja={result.conflicts}; prva primjera:")
        for example in result.examples:
            print(f"  - {example}")
    print("UVOZ PRIMIJENJEN." if apply else "SUHI POKUS — baza nije promijenjena.")
    print("Osobne količine, napomene i popis izdanja nisu mijenjani.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dopuna Koala Kollect metapodataka")
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--download", action="store_true", help="preuzmi i provjeri JSONL snapshot")
    group.add_argument("--apply", action="store_true", help="upiši promjene u jednoj transakciji")
    args = parser.parse_args()
    try:
        if args.download:
            timestamp = download_snapshot(args.snapshot_dir)
            print(f"Preuzimanje i SHA-256 provjera uspješni ({timestamp})")
            print(f"Spremljeno u: {args.snapshot_dir.resolve()}")
            print("Nije uspostavljena veza s bazom; pokreni bez opcija za pregled.")
        else:
            asyncio.run(_run(args.snapshot_dir, args.apply))
    except (EnrichmentError, OSError) as exc:
        parser.exit(1, f"GREŠKA: {exc}\n")


if __name__ == "__main__":
    main()
