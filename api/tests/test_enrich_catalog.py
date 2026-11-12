"""Korak 7: sve provjere rade lokalno na SQLiteu (bez mreže i korisničke baze)."""
import asyncio
import hashlib
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.enrich_catalog import (
    EnrichmentError, EnrichmentRow, _validate_file, enrich_rows,
    load_snapshot, parse_enrichment, recognize_keywords,
)
from app.models import (
    Base, Archetype, Attribute, Card, CardPrinting, CardSet, CollectionEntry,
    Color, Keyword, User,
)
from app.seed import ATTRIBUTES, COLORS, KEYWORDS


class DbBridge:
    """Slično ostalim testovima projekta, AsyncSession adapter za SQLite."""
    def __init__(self, sync_session):
        self.session = sync_session

    async def scalars(self, stmt):
        return self.session.scalars(stmt)

    def add(self, obj):
        self.session.add(obj)


def sample_jsonl():
    card = {"key": "card_example123", "number": "OP01-016", "category": "character"}
    obs = {
        "key": "obs1", "card_key": "card_example123", "site": "en", "name": "Nami",
        "category": "character", "colors": ["red"], "attributes": ["special"],
        "types": ["Straw Hat Crew", "East Blue"], "cost": 1, "power": 2000,
        "counter": 1000, "effect": "[On Play] Draw 1 card. [DON!! x1] [Your Turn] [Rush]",
        "trigger": "[Trigger] Activate this card.",
    }
    printing = {
        "key": "prt_one", "card_key": "card_example123", "variant": "base",
        "image_url": "https://en.onepiece-cardgame.com/images/cardlist/card/OP01-016.png",
        "block_icon": 1,
    }
    return {
        "data/cards.jsonl": [card],
        "data/card_observations/en.jsonl": [obs],
        "data/printings/en.jsonl": [printing],
    }


def one_row():
    records, _ = parse_enrichment(sample_jsonl())
    return records[0]


def setup_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = Session(engine)
    op01 = CardSet(code="OP01", name="OP01", sort_order=1)
    red = Color(name="Red")
    s.add_all([op01, *[Color(name=n) for n in COLORS if n != "Red"], red])
    s.add_all(Attribute(name=n) for n in ATTRIBUTES)
    s.add_all(Keyword(name=n) for n in KEYWORDS)
    card = Card(code="OP01-016", name="Nami", original_set=op01, colors=[red], color="Red")
    p = CardPrinting(card=card, product_set=op01, variant_code="regular", rarity="R",
                     image_url="https://en.onepiece-cardgame.com/images/cardlist/card/OP01-016.png")
    s.add(p)
    s.flush()
    user = User(username="collector", password_hash="hash", role="user")
    s.add(user)
    s.flush()
    s.add(CollectionEntry(user_id=user.id, printing_id=p.id, quantity=3, note="Posebna napomena"))
    s.commit()
    return engine, s


def test_snapshot_validation_sha_and_count(tmp_path):
    raw = sample_jsonl()
    files = {}
    for name, rows in raw.items():
        body = b"".join((json.dumps(r) + "\n").encode("utf-8") for r in rows)
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        files[name] = {"rows": len(rows), "sha256": hashlib.sha256(body).hexdigest()}
    (tmp_path / "manifest.json").write_text(
        json.dumps({"generated_at": "2026-11-01T00:00:00Z", "files": files}), encoding="utf-8"
    )
    result, date = load_snapshot(tmp_path)
    assert result == raw
    assert date == "2026-11-01T00:00:00Z"
    bad_file = tmp_path / "data/cards.jsonl"
    bad_file.write_text(bad_file.read_text() + "{}\n", encoding="utf-8")
    with pytest.raises(EnrichmentError, match="SHA-256"):
        load_snapshot(tmp_path)


def test_parse_enrichment_real_style_koala_records():
    rows, info = parse_enrichment(sample_jsonl())
    assert len(rows) == 1
    r = rows[0]
    assert r.code == "OP01-016"
    assert (r.cost, r.power, r.counter) == (1, 2000, 1000)
    assert r.archetypes == ("Straw Hat Crew", "East Blue")
    assert r.attributes == ("Special",)
    assert r.category == "Character"
    assert r.block_icon == "1"
    assert "[Trigger]" in r.effect_text
    assert {"On Play", "Your Turn", "Rush", "DON!! xN", "Trigger"} <= set(r.keywords)
    assert info["koala_cards"] == 1


def test_unnumbered_don_is_skipped_without_fake_id():
    sample = sample_jsonl()
    sample["data/cards.jsonl"].append({"key": "don123", "don_design": "promo:test"})
    rows, info = parse_enrichment(sample)
    assert len(rows) == 1
    assert info["unnumbered_or_don"] == 1


def test_superseded_observation_is_not_used():
    sample = sample_jsonl()
    sample["data/card_observations/en.jsonl"].append({
        "card_key": "card_example123", "name": "Old name", "superseded_at": "2026-10-01T00:00:00Z"})
    rows, _ = parse_enrichment(sample)
    assert rows[0].name == "Nami"


def test_duplicate_live_observations_fail_closed():
    sample = sample_jsonl()
    sample["data/card_observations/en.jsonl"].append({
        "card_key": "card_example123", "name": "Different current name"})
    with pytest.raises(EnrichmentError, match="Više aktivnih"):
        parse_enrichment(sample)


def test_counter_keyword_is_not_numeric_counter():
    tags = recognize_keywords("This Character gets +1000 counter. [Blocker]", "")
    assert "Counter" not in tags
    assert "Blocker" in tags
    tags = recognize_keywords("[Counter] +4000. [DON!! −2] Trash 1 card.", "")
    assert "Counter" in tags
    assert "DON!! -N" in tags
    assert "Trash" in tags


def test_dry_run_keeps_all_values_unchanged():
    engine, s = setup_db()
    try:
        result = asyncio.run(enrich_rows(DbBridge(s), [one_row()], apply=False))
        s.commit()
        assert result.matched == 1 and result.cards_updated == 1
        card = s.scalars(select(Card)).one()
        assert card.cost is None
        assert s.scalars(select(Archetype)).all() == []
        printing = s.scalars(select(CardPrinting)).one()
        assert printing.block_icon is None
    finally:
        s.close()
        engine.dispose()


def test_apply_idempotency_and_personal_collection_unchanged():
    engine, s = setup_db()
    try:
        first = asyncio.run(enrich_rows(DbBridge(s), [one_row()], apply=True))
        s.commit()
        assert first.matched == 1
        assert first.archetypes_created == 2
        assert first.block_icons_filled == 1
        card = s.scalars(select(Card)).one()
        assert card.cost == 1 and card.power == 2000 and card.counter == 1000
        assert card.card_type == "Character"
        assert {a.name for a in card.archetypes} == {"Straw Hat Crew", "East Blue"}
        assert {a.name for a in card.keywords} >= {"On Play", "Rush", "Trigger"}
        assert s.scalars(select(CardPrinting)).one().block_icon == "1"
        collection = s.scalars(select(CollectionEntry)).one()
        assert (collection.quantity, collection.note) == (3, "Posebna napomena")
        second = asyncio.run(enrich_rows(DbBridge(s), [one_row()], apply=True))
        s.commit()
        assert (second.cards_updated, second.fields_filled, second.relations_added,
                second.archetypes_created, second.block_icons_filled) == (0, 0, 0, 0, 0)
        assert s.scalars(select(CollectionEntry)).one().quantity == 3
    finally:
        s.close()
        engine.dispose()


def test_does_not_replace_conflicting_existing_data_or_wrong_block_image():
    engine, s = setup_db()
    try:
        card = s.scalars(select(Card)).one()
        card.cost = 9
        s.commit()
        original = one_row()
        changed_image = EnrichmentRow(**{**vars(original), "base_image_url": "https://example.com/a.png"})
        result = asyncio.run(enrich_rows(DbBridge(s), [changed_image], apply=True))
        s.commit()
        assert result.conflicts >= 1
        assert card.cost == 9
        assert s.scalars(select(CardPrinting)).one().block_icon is None
    finally:
        s.close()
        engine.dispose()


def test_does_not_create_unknown_cards_or_printings():
    engine, s = setup_db()
    try:
        original = one_row()
        unknown = EnrichmentRow(**{**vars(original), "code": "OP17-001"})
        result = asyncio.run(enrich_rows(DbBridge(s), [unknown], apply=True))
        s.commit()
        assert (result.unmatched, result.matched) == (1, 0)
        assert len(s.scalars(select(Card)).all()) == 1
        assert len(s.scalars(select(CardPrinting)).all()) == 1
    finally:
        s.close()
        engine.dispose()


def test_color_conflict_preserves_existing_red():
    engine, s = setup_db()
    try:
        original = one_row()
        mismatch = EnrichmentRow(**{**vars(original), "colors": ("Yellow",)})
        result = asyncio.run(enrich_rows(DbBridge(s), [mismatch], apply=True))
        s.commit()
        assert result.conflicts >= 1
        card = s.scalars(select(Card)).one()
        assert {c.name for c in card.colors} == {"Red"}
    finally:
        s.close()
        engine.dispose()


def test_bad_numeric_values_refuse_entire_snapshot():
    sample = sample_jsonl()
    sample["data/card_observations/en.jsonl"][0]["power"] = "six thousand"
    with pytest.raises(EnrichmentError, match="power"):
        parse_enrichment(sample)
