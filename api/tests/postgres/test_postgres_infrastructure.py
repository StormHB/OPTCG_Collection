"""Korak 11C.1: osnovni testovi stvarne izolirane PostgreSQL baze."""

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.test_database import (
    EXPECTED_CLUSTER_NAME,
    EXPECTED_DATABASE,
    EXPECTED_USER,
    inspect_test_database,
)

pytestmark = pytest.mark.postgres


def _run(coroutine):
    return asyncio.run(coroutine)


def test_connection_uses_expected_postgres_16_database(postgres_database_url):
    identity = _run(inspect_test_database(postgres_database_url))
    assert identity.database == EXPECTED_DATABASE
    assert identity.user == EXPECTED_USER
    assert identity.server_version_num >= 160000
    assert identity.cluster_name == EXPECTED_CLUSTER_NAME


def test_alembic_schema_is_at_004_head(postgres_database_url):
    async def check_revision():
        engine = create_async_engine(postgres_database_url)
        try:
            async with engine.connect() as connection:
                return await connection.scalar(
                    text("SELECT version_num FROM alembic_version")
                )
        finally:
            await engine.dispose()

    assert _run(check_revision()) == "004"


def test_insert_select_and_rollback_are_isolated(postgres_database_url):
    username = f"postgres_11c1_{uuid.uuid4().hex}"

    async def exercise_transaction():
        engine = create_async_engine(postgres_database_url)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                await connection.execute(
                    text(
                        "INSERT INTO users "
                        "(username, password_hash, role, is_active) "
                        "VALUES (:username, :password_hash, 'user', true)"
                    ),
                    {"username": username, "password_hash": "test-only-hash"},
                )
                assert (
                    await connection.scalar(
                        text("SELECT username FROM users WHERE username = :username"),
                        {"username": username},
                    )
                    == username
                )
                await transaction.rollback()

            async with engine.connect() as connection:
                return await connection.scalar(
                    text("SELECT count(*) FROM users WHERE username = :username"),
                    {"username": username},
                )
        finally:
            await engine.dispose()

    assert _run(exercise_transaction()) == 0
