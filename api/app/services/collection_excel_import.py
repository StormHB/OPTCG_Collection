"""Siguran uvoz osobne Excel kolekcije: prvo preview, zatim potvrđeni apply.

Nije uvoz zajedničkog kataloga. Ni `cards` ni `card_printings` se ne mijenjaju.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from openpyxl import load_workbook
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.card import Card
from app.models.card_printing import CardPrinting
from app.models.card_set import CardSet
from app.models.collection_entry import CollectionEntry
from app.models.card_loan import CardLoan

ImportMode = Literal["replace", "add"]
MAX_UPLOAD_BYTES = 6 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 60 * 1024 * 1024
MAX_SHEETS = 100
MAX_TOTAL_ROWS = 30_000
MAX_IMPORT_QUANTITY = 999_999
MAX_SAMPLE_ROWS = 25
MAX_ISSUES_DISPLAY = 60

SET_SHEET_PATTERN = re.compile(r"^(?:(?:OP|EB|ST|PRB)\d{2}|P)$", re.IGNORECASE)
CARD_CODE_PATTERN = re.compile(r"^(?:(?:OP|EB|ST|PRB)\d{2}|P)-\d{3}$", re.IGNORECASE)
SKIP_SHEETS = {"PREGLED", "SUMMARY", "PREGLED KOLEKCIJE", "OVERVIEW"}
SPECIAL_SHEETS = {"VARIJANTE", "DON", "DON!!"}


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).split())


HEADERS = {
    "broj karte": "code", "number": "code", "card number": "code", "card code": "code",
    "kolicina": "quantity", "quantity": "quantity", "qty": "quantity",
    "napomena": "note", "note": "note",
    "printing_id": "printing_id", "printing id": "printing_id", "id izdanja": "printing_id",
    "set izdanja": "set_code", "product set": "set_code", "set": "set_code",
}


@dataclass(frozen=True)
class ExcelEntry:
    sheet: str
    row: int
    card_code: str
    quantity: int
    note: str | None
    printing_id: int | None = None
    product_set: str | None = None


@dataclass(frozen=True)
class ImportIssue:
    sheet: str
    row: int | None
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"

    def as_dict(self) -> dict:
        return {"sheet": self.sheet, "row": self.row, "code": self.code,
                "message": self.message, "severity": self.severity}


@dataclass
class ParsedWorkbook:
    entries: list[ExcelEntry] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    sheets_read: int = 0
    blank_rows_skipped: int = 0


@dataclass(frozen=True)
class CatalogPrinting:
    printing_id: int
    card_code: str
    product_set: str
    variant: str


@dataclass(frozen=True)
class PlannedChange:
    sheet: str
    row: int
    card_code: str
    printing_id: int
    quantity_in_file: int
    before_quantity: int | None
    after_quantity: int
    before_note: str | None
    after_note: str | None
    action: Literal["create", "update", "unchanged", "skip_zero"]

    def as_sample(self) -> dict:
        return {
            "sheet": self.sheet, "row": self.row, "card_code": self.card_code,
            "printing_id": self.printing_id, "quantity_in_file": self.quantity_in_file,
            "before_quantity": self.before_quantity, "after_quantity": self.after_quantity,
            "action": self.action,
        }


@dataclass
class ImportPlan:
    mode: ImportMode
    file_sha256: str
    user_id: int
    parsed: ParsedWorkbook
    changes: list[PlannedChange]
    issues: list[ImportIssue]

    @property
    def token(self) -> str:
        """Vezan uz XLSX bytes + način uvoza + korisnika + trenutno stanje relevantnih redaka.

        Ako se stanje promijeni između previewa i applya, token se mijenja.
        Datoteka se šalje ponovo: nema pohrane uploadova ili sesije na serveru.
        """
        raw = {
            "file": self.file_sha256, "user": self.user_id, "mode": self.mode,
            "changes": [vars(row) for row in self.changes],
            "issues": [issue.as_dict() for issue in self.issues],
        }
        return hashlib.sha256(
            json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    @property
    def errors(self) -> list[ImportIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def summary(self) -> dict:
        counts = {name: sum(c.action == name for c in self.changes)
                  for name in ("create", "update", "unchanged", "skip_zero")}
        return {
            "mode": self.mode,
            "can_apply": len(self.errors) == 0,
            "file_sha256": self.file_sha256,
            "plan_token": self.token,
            "sheets_read": self.parsed.sheets_read,
            "rows_with_quantity": len(self.parsed.entries),
            "blank_rows_skipped": self.parsed.blank_rows_skipped,
            "matched": len(self.changes),
            "create": counts["create"], "update": counts["update"],
            "unchanged": counts["unchanged"], "skip_zero": counts["skip_zero"],
            "error_count": len(self.errors),
            "warning_count": len(self.issues) - len(self.errors),
            "issues": [issue.as_dict() for issue in self.issues[:MAX_ISSUES_DISPLAY]],
            "issues_truncated": len(self.issues) > MAX_ISSUES_DISPLAY,
            "samples": [c.as_sample() for c in self.changes[:MAX_SAMPLE_ROWS]],
        }


def _check_zip_safety(content: bytes) -> None:
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise AppError("invalid_excel", "Excel datoteka je prazna ili veća od 6 MB", 422)
    if not content.startswith(b"PK"):
        raise AppError("invalid_excel", "Potrebna je prava .xlsx datoteka", 422)
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > 3000:
                raise AppError("invalid_excel", "Excel sadrži previše zapisa", 422)
            if sum(info.file_size for info in members) > MAX_UNCOMPRESSED_BYTES:
                raise AppError("invalid_excel", "Excel je prevelik nakon raspakiravanja", 422)
            if "[Content_Types].xml" not in archive.namelist():
                raise AppError("invalid_excel", "Datoteka nije valjana .xlsx arhiva", 422)
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise AppError("invalid_excel", "Neispravna ili oštećena .xlsx datoteka", 422) from exc


def _int_cell(value: object, *, allow_blank: bool) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if allow_blank:
            return None
        raise ValueError("Nedostaje vrijednost")
    if isinstance(value, bool):
        raise ValueError("Vrijednost mora biti cijeli broj")
    if isinstance(value, int):
        result = value
    elif isinstance(value, float) and value.is_integer():
        result = int(value)
    elif isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        result = int(value.strip())
    else:
        raise ValueError("Vrijednost mora biti nenegativan cijeli broj")
    if result < 0 or result > MAX_IMPORT_QUANTITY:
        raise ValueError("Količina mora biti između 0 i 999999")
    return result


def parse_excel(content: bytes, filename: str) -> ParsedWorkbook:
    """Učitavanje samo vrijednosti, bez pokretanja Excel makroa ili formula."""
    if not filename.lower().endswith(".xlsx"):
        raise AppError("invalid_excel", "Podržan je samo .xlsx format", 422)
    _check_zip_safety(content)
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
    except Exception as exc:
        raise AppError("invalid_excel", "Excel nije moguće pročitati", 422) from exc

    parsed = ParsedWorkbook()
    seen_sheet_code: set[tuple[str, str]] = set()
    note_only_counts: Counter[str] = Counter()
    total_rows = 0
    try:
        if len(wb.sheetnames) > MAX_SHEETS:
            raise AppError("invalid_excel", "Previše sheetova u Excel datoteci", 422)
        for ws in wb.worksheets:
            sheet = ws.title.strip().upper()
            if sheet in SKIP_SHEETS:
                continue
            if not SET_SHEET_PATTERN.fullmatch(sheet) and sheet not in SPECIAL_SHEETS:
                # Ne preskači tiho podatke iz nepoznatih sheetova.
                has_rows = any(
                    any(value is not None and str(value).strip() for value in cells)
                    for cells in ws.iter_rows(min_row=2, max_row=min(ws.max_row, 1000), values_only=True)
                )
                parsed.issues.append(ImportIssue(
                    ws.title, None, "unsupported_sheet",
                    "Nepodržan sheet s podacima" if has_rows else "Prazan nepoznati sheet preskočen",
                    "error" if has_rows else "warning",
                ))
                continue
            parsed.sheets_read += 1
            iterator = ws.iter_rows(values_only=True)
            header = next(iterator, None)
            if header is None:
                continue
            columns = {_norm(name): ix for ix, name in enumerate(header) if name is not None}
            mapped = {mapped: columns[label] for label, mapped in HEADERS.items() if label in columns}
            if "quantity" not in mapped or ("code" not in mapped and "printing_id" not in mapped):
                parsed.issues.append(ImportIssue(ws.title, 1, "missing_columns",
                                                 "Nedostaju stupci Broj karte i/ili Količina"))
                continue
            # Za posebne sheetove u svakom popunjenom retku tražimo ID
            # konkretnog izdanja; nije dovoljno imati samo stupac s tim naslovom.
            must_have_printing_id = sheet in SPECIAL_SHEETS
            for row_index, cells in enumerate(iterator, start=2):
                total_rows += 1
                if total_rows > MAX_TOTAL_ROWS:
                    raise AppError("invalid_excel", "Excel ima previše redaka", 422)
                def get(name: str):
                    ix = mapped.get(name)
                    return cells[ix] if ix is not None and ix < len(cells) else None
                raw_qty = get("quantity")
                raw_code = get("code")
                raw_note = get("note")
                raw_id = get("printing_id")
                if raw_qty is None or (isinstance(raw_qty, str) and not raw_qty.strip()):
                    if raw_note is not None and str(raw_note).strip():
                        note_only_counts[ws.title] += 1
                    parsed.blank_rows_skipped += 1
                    continue
                try:
                    quantity = _int_cell(raw_qty, allow_blank=False)
                except ValueError as exc:
                    parsed.issues.append(ImportIssue(ws.title, row_index, "invalid_quantity", str(exc)))
                    continue
                code = str(raw_code or "").strip().upper()
                if not code and raw_id is None:
                    parsed.issues.append(ImportIssue(ws.title, row_index, "missing_code",
                                                     "Nedostaje broj karte ili ID izdanja"))
                    continue
                if code and not (CARD_CODE_PATTERN.fullmatch(code) or sheet in {"DON", "DON!!"}):
                    parsed.issues.append(ImportIssue(ws.title, row_index, "invalid_code",
                                                     f"Neispravan broj karte: {code}"))
                    continue
                if raw_note is not None and not isinstance(raw_note, str):
                    parsed.issues.append(ImportIssue(ws.title, row_index, "invalid_note",
                                                     "Napomena mora biti tekst"))
                    continue
                note = raw_note.strip() if isinstance(raw_note, str) and raw_note.strip() else None
                if note is not None and len(note) > 1000:
                    parsed.issues.append(ImportIssue(ws.title, row_index, "long_note",
                                                     "Napomena može imati najviše 1000 znakova"))
                    continue
                printing_id = None
                if raw_id is not None and str(raw_id).strip():
                    try:
                        printing_id = _int_cell(raw_id, allow_blank=False)
                        if printing_id == 0:
                            raise ValueError("ID izdanja mora biti veći od nule")
                    except ValueError as exc:
                        parsed.issues.append(ImportIssue(ws.title, row_index, "invalid_printing_id", str(exc)))
                        continue
                elif must_have_printing_id:
                    parsed.issues.append(ImportIssue(ws.title, row_index, "missing_printing_id",
                                                     "Za VARIJANTE/DON potreban je stupac ID izdanja s točnim ID-jem"))
                    continue
                product_set = str(get("set_code") or "").strip().upper() or None
                key = (sheet, str(printing_id) if printing_id is not None else code)
                if key in seen_sheet_code:
                    parsed.issues.append(ImportIssue(ws.title, row_index, "duplicate_row",
                                                     "Ista karta/izdanje pojavljuje se više puta u sheetu"))
                    continue
                seen_sheet_code.add(key)
                parsed.entries.append(ExcelEntry(ws.title, row_index, code, quantity,
                                                 note, printing_id, product_set))
    finally:
        wb.close()
    for sheet_name, count in note_only_counts.items():
        parsed.issues.append(ImportIssue(
            sheet_name, None, "note_without_quantity_ignored",
            f"Preskočeno {count} redaka s napomenom bez količine", "warning"
        ))
    if parsed.sheets_read == 0:
        raise AppError("invalid_excel", "Nijedan podržani sheet nije pronađen", 422)
    return parsed


async def build_plan(
    db: AsyncSession, user_id: int, content: bytes, filename: str, mode: ImportMode,
) -> ImportPlan:
    parsed = parse_excel(content, filename)
    records = (await db.execute(
        select(CardPrinting.id, Card.code, CardSet.code, CardPrinting.variant_code)
        .join(Card, Card.id == CardPrinting.card_id)
        .join(CardSet, CardSet.id == CardPrinting.product_set_id)
    )).all()
    by_id: dict[int, CatalogPrinting] = {}
    regular_by_sheet_code: dict[tuple[str, str], list[CatalogPrinting]] = {}
    for pid, code, set_code, variant in records:
        printing = CatalogPrinting(pid, code.upper(), set_code.upper(), variant)
        by_id[pid] = printing
        if variant.casefold() == "regular":
            regular_by_sheet_code.setdefault((set_code.upper(), code.upper()), []).append(printing)
    existing = {entry.printing_id: entry for entry in
                (await db.scalars(select(CollectionEntry).where(CollectionEntry.user_id == user_id))).all()}

    # Aktivne odlazne posudbe ne smiju biti izgubljene Excel replace uvozom.
    loaned_rows = (await db.execute(
        select(CardLoan.printing_id, func.sum(CardLoan.quantity - CardLoan.quantity_returned))
        .where(CardLoan.user_id == user_id, CardLoan.direction == "lent")
        .group_by(CardLoan.printing_id)
    )).all()
    loaned_by_printing = {pid: int(qty) for pid, qty in loaned_rows}

    issues = list(parsed.issues)
    changes = []
    seen_ids: set[int] = set()
    for row in parsed.entries:
        sheet = row.sheet.strip().upper()
        if row.printing_id is not None:
            printing = by_id.get(row.printing_id)
            if printing is None or (row.card_code and printing.card_code != row.card_code):
                issues.append(ImportIssue(row.sheet, row.row, "unknown_printing_id",
                                          "ID izdanja nije pronađen ili ne odgovara broju karte"))
                continue
            if sheet not in {"VARIJANTE", "DON", "DON!!"} and printing.product_set != sheet:
                issues.append(ImportIssue(row.sheet, row.row, "wrong_set",
                                          "ID izdanja ne pripada setu sheeta"))
                continue
        else:
            matches = regular_by_sheet_code.get((sheet, row.card_code), [])
            if not matches:
                issues.append(ImportIssue(row.sheet, row.row, "missing_printing",
                                          f"Nije pronađeno regular izdanje {row.card_code} u setu {sheet}"))
                continue
            if len(matches) != 1:
                issues.append(ImportIssue(row.sheet, row.row, "ambiguous_printing",
                                          "Više izdanja odgovara retku; potreban je ID izdanja"))
                continue
            printing = matches[0]
        if row.product_set and printing.product_set != row.product_set:
            issues.append(ImportIssue(row.sheet, row.row, "wrong_set",
                                      f"ID izdanja nije iz seta {row.product_set}"))
            continue
        if printing.printing_id in seen_ids:
            issues.append(ImportIssue(row.sheet, row.row, "duplicate_printing",
                                      "Isto fizičko izdanje navedeno je više puta u datoteci"))
            continue
        seen_ids.add(printing.printing_id)
        current = existing.get(printing.printing_id)
        before = current.quantity if current is not None else None
        before_note = current.note if current is not None else None
        after = row.quantity if mode == "replace" else (before or 0) + row.quantity
        if after < loaned_by_printing.get(printing.printing_id, 0):
            issues.append(ImportIssue(
                row.sheet, row.row, "active_loans_exceed_owned",
                "Kolicina u Excelu manja je od jos posudenih primjeraka"
            ))
            continue
        if after > MAX_IMPORT_QUANTITY:
            issues.append(ImportIssue(row.sheet, row.row, "quantity_overflow",
                                      "Nakon zbrajanja količina prelazi 999999"))
            continue
        # Namjerno ne brišemo postojeću napomenu praznom ćelijom iz Excela.
        # U add načinu postojeće napomene se nikad ne prepisuju.
        after_note = (row.note if row.note is not None else before_note) if mode == "replace" else (
            before_note if current is not None else row.note
        )
        if current is None and after == 0 and after_note is None:
            action = "skip_zero"
        elif current is None:
            action = "create"
        elif current.quantity == after and current.note == after_note:
            action = "unchanged"
        else:
            action = "update"
        changes.append(PlannedChange(row.sheet, row.row, row.card_code,
                                     printing.printing_id, row.quantity, before, after,
                                     before_note, after_note, action))
    return ImportPlan(mode, hashlib.sha256(content).hexdigest(), user_id, parsed, changes, issues)


async def apply_plan(db: AsyncSession, plan: ImportPlan, expected_token: str) -> dict:
    if plan.errors:
        raise AppError("import_has_errors",
                       "Datoteka sadrži greške; prvo pregledaj preview i ispravi retke", 422)
    if plan.token != expected_token:
        raise AppError("stale_import_preview",
                       "Datoteka, način uvoza ili kolekcija promijenili su se nakon previewa", 409)
    # Serijaliziraj Excel apply s kreiranjem novih posudbi.
    # Zakljucaj sve postojece retke u deterministickom poretku, jednim upitom.
    changes_to_write = [c for c in plan.changes if c.action in {"create", "update"}]
    existing_ids = sorted(c.printing_id for c in changes_to_write if c.before_quantity is not None)
    locked_entries = {} if not existing_ids else {
        entry.printing_id: entry for entry in (await db.scalars(
            select(CollectionEntry).where(
                CollectionEntry.user_id == plan.user_id,
                CollectionEntry.printing_id.in_(existing_ids),
            ).order_by(CollectionEntry.printing_id).with_for_update()
            .execution_options(populate_existing=True)
        )).all()
    }
    for change in changes_to_write:
        if change.before_quantity is not None:
            current = locked_entries.get(change.printing_id)
            if (current is None or current.quantity != change.before_quantity
                    or current.note != change.before_note):
                raise AppError("stale_import_preview", "Kolekcija se promijenila", 409)

    # Posudbe mogu nastati nakon previewa. Provjera opet pod istim lockom.
    changed_ids = [c.printing_id for c in changes_to_write]
    active_rows = [] if not changed_ids else (await db.execute(
        select(CardLoan.printing_id,
               func.sum(CardLoan.quantity - CardLoan.quantity_returned))
        .where(CardLoan.user_id == plan.user_id, CardLoan.direction == "lent",
               CardLoan.printing_id.in_(changed_ids))
        .group_by(CardLoan.printing_id)
    )).all()
    active_by_printing = {pid: int(qty) for pid, qty in active_rows}
    for change in changes_to_write:
        if change.after_quantity < active_by_printing.get(change.printing_id, 0):
            raise AppError(
                "active_loans_exceed_owned",
                "Excel uvoz bi smanjio kolicinu ispod broja aktivnih posudbi",
                409,
            )
    for change in plan.changes:
        if change.action in {"unchanged", "skip_zero"}:
            continue
        if change.action == "create":
            db.add(CollectionEntry(
                user_id=plan.user_id, printing_id=change.printing_id,
                quantity=change.after_quantity, note=change.after_note,
            ))
        else:
            current = await db.scalar(select(CollectionEntry).where(
                CollectionEntry.user_id == plan.user_id,
                CollectionEntry.printing_id == change.printing_id,
            ))
            if current is None:
                raise AppError("stale_import_preview", "Kolekcija se promijenila", 409)
            current.quantity = change.after_quantity
            current.note = change.after_note
    try:
        await db.flush()
    except IntegrityError:
        # get_db dependency radi rollback transakcije ako upis ne prođe.
        raise AppError("import_conflict", "Sukob pri istovremenom uvozu kolekcije", 409) from None
    return {"status": "applied", **plan.summary()}
