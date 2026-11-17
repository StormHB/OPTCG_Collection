"""Fixtureovi samo za namjensku PostgreSQL testnu bazu."""

import asyncio
import os

import pytest

from app.core.test_database import configured_test_database_url, inspect_test_database
from app.prepare_test_database import prepare_test_database


@pytest.fixture(scope="session")
def postgres_database_url() -> str:
    required = os.getenv("POSTGRES_TEST_REQUIRED") == "1"
    url = configured_test_database_url(required=required)
    if url is None:
        pytest.skip("TEST_DATABASE_URL nije postavljen; db_test nije zatrazena")

    asyncio.run(inspect_test_database(url))
    prepare_test_database(url)
    return url
