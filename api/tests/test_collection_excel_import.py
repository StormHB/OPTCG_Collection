"""Korak 8B: Excel, mapiranje izdanja, preview/apply, privatnost i sigurnost."""

import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.models import Base, Card, CardPrinting, CardSet, CollectionEntry, User
from app.routers.collections import router as collections_router
from app.services.collection_excel_import import (
    apply_plan, build_plan, parse_excel,
)


class DbAdapter:
    """Async protokol nad sinkronom SQLite sesijom (kao u testovima 8A)."""

    def __init__(self, session):
        self.session = session

    async def execute(self, query):
        return self.session.execute(query)

    async def scalars(self, query):
        return self.session.scalars(query)

    async def scalar(self, query):
        return self.session.scalar(query)

    def add(self, obj):
        self.session.add(obj)

    async def flush(self):
        self.session.flush()


def excel_bytes(op01=3, prb01=2, *, variant_qty=None, variant_id=None,
                note="Za deck", extra_op01=None):
    wb = Workbook()
    overview = wb.active
    overview.title = "PREGLED"
    overview.append(["Set", "Ukupno komada"])
    overview.append(["UKUPNO", 999])  # mora biti ignoriran
    op = wb.create_sheet("OP01")
    op.append(["Broj karte", "Ime karte", "Boja", "Količina", "Rijetkost", "Slika", "Napomena"])
    op.append(["OP01-016", "Nami", "Red", op01, "R", None, note])
    if extra_op01 is not None:
        op.append(["OP01-016", "Nami", "Red", extra_op01, "R", None, None])
    prb = wb.create_sheet("PRB01")
    prb.append(["Broj karte", "Ime karte", "Boja", "Količina", "Rijetkost", "Slika", "Napomena"])
    prb.append(["OP01-016", "Nami", "Red", prb01, "R", None, None])
    variants = wb.create_sheet("VARIJANTE")
    variants.append(["Broj karte", "Količina", "Napomena", "ID izdanja"])
    if variant_qty is not None:
        variants.append(["OP01-016", variant_qty, None, variant_id])
    data = BytesIO()
    wb.save(data)
    wb.close()
    return data.getvalue()


@pytest.fixture()
def catalog():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        s1 = CardSet(code="OP01", name="OP01", sort_order=1)
        s2 = CardSet(code="PRB01", name="PRB01", sort_order=2)
        card = Card(code="OP01-016", name="Nami", original_set=s1)
        orig = CardPrinting(card=card, product_set=s1, variant_code="regular")
        reprint = CardPrinting(card=card, product_set=s2, variant_code="regular")
        alt = CardPrinting(card=card, product_set=s1, variant_code="alt-art")
        owner = User(username="owner", password_hash="x", role="user")
        other = User(username="other", password_hash="x", role="user")
        session.add_all([orig, reprint, alt, owner, other])
        session.commit()
        yield session, owner, other, orig, reprint, alt
    engine.dispose()


def run(coro):
    return asyncio.run(coro)


def test_parser_reads_real_sheet_layout_and_ignores_overview():
    parsed = parse_excel(excel_bytes(), "collection.xlsx")
    assert [(r.sheet, r.card_code, r.quantity) for r in parsed.entries] == [
        ("OP01", "OP01-016", 3), ("PRB01", "OP01-016", 2)]
    assert parsed.sheets_read == 3
    assert parsed.issues == []


def test_preview_does_not_write_and_distinguishes_reprint(catalog):
    session, owner, _, orig, reprint, _ = catalog
    plan = run(build_plan(DbAdapter(session), owner.id, excel_bytes(), "list.xlsx", "replace"))
    assert plan.summary()["can_apply"] is True
    assert plan.summary()["create"] == 2
    assert {c.printing_id for c in plan.changes} == {orig.id, reprint.id}
    assert session.scalars(select(CollectionEntry)).all() == []
    assert len(plan.token) == 64


def test_apply_creates_only_owner_entries_and_preview_repeats_as_unchanged(catalog):
    session, owner, other, orig, reprint, _ = catalog
    data = excel_bytes()
    db = DbAdapter(session)
    plan = run(build_plan(db, owner.id, data, "list.xlsx", "replace"))
    result = run(apply_plan(db, plan, plan.token))
    session.commit()
    assert (result["create"], result["update"]) == (2, 0)
    stored = {entry.printing_id: entry.quantity for entry in session.scalars(
        select(CollectionEntry).where(CollectionEntry.user_id == owner.id)).all()}
    assert stored == {orig.id: 3, reprint.id: 2}
    assert session.scalars(select(CollectionEntry).where(CollectionEntry.user_id == other.id)).all() == []
    after = run(build_plan(db, owner.id, data, "list.xlsx", "replace"))
    assert after.summary()["unchanged"] == 2
    assert after.token != plan.token


def test_add_accumulates_quantities_but_does_not_override_note(catalog):
    session, owner, _, orig, _, _ = catalog
    session.add(CollectionEntry(user_id=owner.id, printing_id=orig.id, quantity=4, note="Važno"))
    session.commit()
    db = DbAdapter(session)
    plan = run(build_plan(db, owner.id, excel_bytes(op01=3), "list.xlsx", "add"))
    target = next(c for c in plan.changes if c.printing_id == orig.id)
    assert target.after_quantity == 7
    assert target.after_note == "Važno"
    run(apply_plan(db, plan, plan.token))
    session.commit()
    assert session.scalar(select(CollectionEntry).where(
        CollectionEntry.user_id == owner.id, CollectionEntry.printing_id == orig.id)).quantity == 7
    with pytest.raises(AppError) as exc:
        run(apply_plan(db, run(build_plan(db, owner.id, excel_bytes(op01=3), "list.xlsx", "add")), plan.token))
    assert exc.value.status_code == 409


def test_replace_only_touches_printings_present_in_file(catalog):
    session, owner, _, orig, reprint, alt = catalog
    session.add_all([
        CollectionEntry(user_id=owner.id, printing_id=orig.id, quantity=9, note="ostaje"),
        CollectionEntry(user_id=owner.id, printing_id=alt.id, quantity=5, note="alt"),
    ])
    session.commit()
    db = DbAdapter(session)
    plan = run(build_plan(db, owner.id, excel_bytes(op01=3), "list.xlsx", "replace"))
    run(apply_plan(db, plan, plan.token))
    session.commit()
    assert session.scalar(select(CollectionEntry).where(CollectionEntry.printing_id == orig.id)).quantity == 3
    assert session.scalar(select(CollectionEntry).where(CollectionEntry.printing_id == orig.id)).note == "Za deck"
    assert session.scalar(select(CollectionEntry).where(CollectionEntry.printing_id == alt.id)).quantity == 5


def test_empty_and_zero_rows_do_not_create_thousands_of_zero_entries(catalog):
    session, owner, _, orig, _, _ = catalog
    db = DbAdapter(session)
    data = excel_bytes(op01=0, prb01=None, note=None)
    plan = run(build_plan(db, owner.id, data, "list.xlsx", "replace"))
    assert plan.summary()["skip_zero"] == 1
    assert plan.summary()["blank_rows_skipped"] >= 1
    run(apply_plan(db, plan, plan.token))
    session.commit()
    assert session.scalars(select(CollectionEntry)).all() == []


def test_existing_entry_can_be_set_to_zero_in_replace(catalog):
    session, owner, _, orig, _, _ = catalog
    session.add(CollectionEntry(user_id=owner.id, printing_id=orig.id, quantity=4, note="keep"))
    session.commit()
    data = excel_bytes(op01=0, prb01=None, note=None)
    db = DbAdapter(session)
    plan = run(build_plan(db, owner.id, data, "list.xlsx", "replace"))
    run(apply_plan(db, plan, plan.token))
    session.commit()
    entry = session.scalar(select(CollectionEntry).where(CollectionEntry.printing_id == orig.id))
    assert entry.quantity == 0 and entry.note == "keep"


def test_variants_require_exact_id_and_can_import_alt_art(catalog):
    session, owner, _, _, _, alt = catalog
    db = DbAdapter(session)
    bad = run(build_plan(db, owner.id, excel_bytes(variant_qty=1), "list.xlsx", "replace"))
    assert bad.summary()["can_apply"] is False
    assert any(i.code == "missing_printing_id" for i in bad.issues)
    with pytest.raises(AppError):
        run(apply_plan(db, bad, bad.token))
    good = run(build_plan(db, owner.id,
                          excel_bytes(variant_qty=1, variant_id=alt.id), "list.xlsx", "replace"))
    assert good.summary()["can_apply"] is True
    assert any(c.printing_id == alt.id for c in good.changes)


def test_missing_printing_blocks_entire_apply(catalog):
    session, owner, *_ = catalog
    data = excel_bytes()
    wb = Workbook()
    sheet = wb.active
    sheet.title = "OP02"
    sheet.append(["Broj karte", "Količina"])
    sheet.append(["OP02-001", 4])
    out = BytesIO()
    wb.save(out)
    wb.close()
    db = DbAdapter(session)
    plan = run(build_plan(db, owner.id, out.getvalue(), "list.xlsx", "replace"))
    assert not plan.summary()["can_apply"]
    assert plan.summary()["error_count"] == 1
    with pytest.raises(AppError):
        run(apply_plan(db, plan, plan.token))
    assert session.scalars(select(CollectionEntry)).all() == []


def test_duplicate_row_fails_preview_and_apply(catalog):
    session, owner, *_ = catalog
    data = excel_bytes(extra_op01=1)
    plan = run(build_plan(DbAdapter(session), owner.id, data, "list.xlsx", "replace"))
    assert any(i.code == "duplicate_row" for i in plan.issues)
    assert plan.summary()["can_apply"] is False


@pytest.mark.parametrize("value", [-1, 2.5, "1,5", True, 1000000])
def test_invalid_quantity_is_reported(value):
    data = excel_bytes(op01=value)
    parsed = parse_excel(data, "list.xlsx")
    assert any(i.code == "invalid_quantity" for i in parsed.issues)


def test_invalid_file_is_rejected():
    with pytest.raises(AppError) as exc:
        parse_excel(b"broken", "list.xlsx")
    assert exc.value.status_code == 422
    with pytest.raises(AppError) as exc:
        parse_excel(excel_bytes(), "list.xlsm")
    assert exc.value.status_code == 422


def test_stale_token_rejects_changed_file(catalog):
    session, owner, *_ = catalog
    db = DbAdapter(session)
    first = run(build_plan(db, owner.id, excel_bytes(op01=2), "list.xlsx", "replace"))
    second = run(build_plan(db, owner.id, excel_bytes(op01=6), "list.xlsx", "replace"))
    with pytest.raises(AppError) as exc:
        run(apply_plan(db, second, first.token))
    assert exc.value.status_code == 409


def test_mode_is_part_of_preview_token(catalog):
    session, owner, *_ = catalog
    data = excel_bytes()
    db = DbAdapter(session)
    replace = run(build_plan(db, owner.id, data, "list.xlsx", "replace"))
    add = run(build_plan(db, owner.id, data, "list.xlsx", "add"))
    assert replace.token != add.token


def test_api_rejects_other_user_before_reading_spreadsheet():
    app = FastAPI()
    app.include_router(collections_router, prefix="/collections")
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    async def dummy_db():
        yield object()

    app.dependency_overrides[get_db] = dummy_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7, role="admin", is_active=True
    )
    client = TestClient(app)
    response = client.post(
        "/collections/8/import/preview",
        files={"file": ("my.xlsx", excel_bytes(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 403


def test_api_preview_accepts_file_and_does_not_modify_db(catalog):
    session, owner, *_ = catalog
    app = FastAPI()
    app.include_router(collections_router, prefix="/collections")
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    async def dummy_db():
        yield DbAdapter(session)

    app.dependency_overrides[get_db] = dummy_db
    app.dependency_overrides[get_current_user] = lambda: owner
    client = TestClient(app)
    response = client.post(
        f"/collections/{owner.id}/import/preview?mode=replace",
        files={"file": ("my.xlsx", excel_bytes(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["create"] == 2
    assert session.scalars(select(CollectionEntry)).all() == []


def test_unknown_sheet_with_data_blocks_apply(catalog):
    session, owner, *_ = catalog
    wb = Workbook()
    ws = wb.active
    ws.title = "MOJ_DODATNI_SHEET"
    ws.append(["Broj karte", "Količina"])
    ws.append(["OP01-016", 2])
    wb.create_sheet("OP01").append(["Broj karte", "Količina"])
    out = BytesIO()
    wb.save(out)
    wb.close()
    plan = run(build_plan(DbAdapter(session), owner.id, out.getvalue(), "list.xlsx", "replace"))
    assert not plan.summary()["can_apply"]
    assert any(i.code == "unsupported_sheet" and i.severity == "error" for i in plan.issues)


def test_api_preview_then_apply_with_matching_token(catalog):
    session, owner, _, orig, reprint, _ = catalog
    app = FastAPI()
    app.include_router(collections_router, prefix="/collections")
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    async def dummy_db():
        yield DbAdapter(session)
        session.commit()

    app.dependency_overrides[get_db] = dummy_db
    app.dependency_overrides[get_current_user] = lambda: owner
    client = TestClient(app)
    file_bytes = excel_bytes()
    file = {"file": ("my.xlsx", file_bytes,
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    preview = client.post(f"/collections/{owner.id}/import/preview", files=file)
    assert preview.status_code == 200
    token = preview.json()["plan_token"]
    applied = client.post(
        f"/collections/{owner.id}/import/apply",
        params={"mode": "replace", "plan_token": token}, files=file,
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "applied"
    rows = {e.printing_id: e.quantity for e in session.scalars(select(CollectionEntry)).all()}
    assert rows == {orig.id: 3, reprint.id: 2}
