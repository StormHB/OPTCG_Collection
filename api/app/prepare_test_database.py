"""Sigurno primijeni Alembic migracije samo na namjenski db_test servis."""

import asyncio
import os
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.core.test_database import inspect_test_database, validate_test_database_url


def prepare_test_database(database_url: str | None = None) -> None:
    url = validate_test_database_url(database_url or os.getenv("TEST_DATABASE_URL"))
    asyncio.run(inspect_test_database(url))

    api_dir = Path(__file__).resolve().parents[1]
    config = Config(api_dir / "alembic.ini")
    config.attributes["test_database_url"] = url
    command.upgrade(config, "head")


if __name__ == "__main__":
    prepare_test_database()
