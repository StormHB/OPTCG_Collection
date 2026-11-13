"""Korak 9A: integritet nove tablice i UTC definicije bez PostgreSQL servera."""

from datetime import timedelta, timezone

import pytest
from sqlalchemy import create_engine, insert, inspect
from sqlalchemy.exc import IntegrityError

from app.core.database import Base
from app.models import CardLoan
from app.models.card_loan import utc_now


@pytest.fixture
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_model_registered_and_has_expected_columns(engine):
    columns = {column["name"] for column in inspect(engine).get_columns("card_loans")}
    assert {"id", "user_id", "printing_id", "direction", "person_name", "quantity",
            "quantity_returned", "loaned_at", "due_at", "returned_at", "note"} == columns


def test_all_datetimes_are_timezone_aware_in_schema():
    for field in ("loaned_at", "due_at", "returned_at"):
        assert CardLoan.__table__.c[field].type.timezone is True
    now = utc_now()
    assert now.tzinfo is timezone.utc
    assert now.utcoffset() == timedelta(0)


def test_outstanding_quantity():
    loan = CardLoan(user_id=1, printing_id=1, direction="lent", person_name="Ivan",
                    quantity=4, quantity_returned=2)
    assert loan.outstanding_quantity == 2
    loan.quantity_returned = 4
    assert loan.outstanding_quantity == 0


@pytest.mark.parametrize("changes", [
    {"quantity": 0},
    {"quantity": -2},
    {"quantity_returned": -1},
    {"quantity_returned": 4},
    {"direction": "other"},
    {"person_name": "   "},
])
def test_invalid_values_rejected_by_database(engine, changes):
    values = {
        "user_id": 1, "printing_id": 1, "direction": "lent", "person_name": "Ivan",
        "quantity": 3, "quantity_returned": 0,
    }
    values.update(changes)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(CardLoan).values(**values))


def test_valid_loan_can_be_inserted(engine):
    with engine.begin() as connection:
        connection.execute(insert(CardLoan).values(
            user_id=1, printing_id=1, direction="borrowed",
            person_name="Marko", quantity=3, quantity_returned=1,
        ))


def test_foreign_keys_reference_expected_tables():
    fks = {fk.target_fullname for fk in CardLoan.__table__.foreign_keys}
    assert fks == {"users.id", "card_printings.id"}
