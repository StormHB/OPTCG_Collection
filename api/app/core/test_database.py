"""Sigurnosne provjere za potpuno odvojenu PostgreSQL testnu bazu."""

import os
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import create_async_engine

EXPECTED_DATABASE = "optcg_test"
EXPECTED_USER = "optcg_test_user"
EXPECTED_HOSTS = frozenset({"127.0.0.1", "localhost"})
EXPECTED_PORT = 5434
EXPECTED_CLUSTER_NAME = "optcg_test_11c"
MIN_POSTGRES_VERSION = 160000

IDENTITY_QUERY = text(
    "SELECT current_database(), current_user, inet_server_port(), "
    "current_setting('server_version_num')::integer, "
    "current_setting('cluster_name')"
)


class UnsafeTestDatabaseError(RuntimeError):
    """Konfiguracija ne dokazuje da je veza namjenska testna baza."""


@dataclass(frozen=True)
class DatabaseIdentity:
    database: str
    user: str
    port: int
    server_version_num: int
    cluster_name: str


def validate_test_database_url(value: str | None) -> str:
    """Odbij sve osim tocno dogovorene lokalne testne konfiguracije."""
    if not value:
        raise UnsafeTestDatabaseError(
            "TEST_DATABASE_URL mora biti izricito postavljen; "
            "DATABASE_URL se ne koristi"
        )

    try:
        url = make_url(value)
    except Exception as exc:
        raise UnsafeTestDatabaseError("TEST_DATABASE_URL nije valjan URL") from exc

    errors = []
    if url.drivername != "postgresql+asyncpg":
        errors.append("driver mora biti postgresql+asyncpg")
    if url.database != EXPECTED_DATABASE:
        errors.append(f"baza mora biti {EXPECTED_DATABASE}")
    if url.username != EXPECTED_USER:
        errors.append(f"korisnik mora biti {EXPECTED_USER}")
    if url.host not in EXPECTED_HOSTS:
        errors.append("host mora biti 127.0.0.1 ili localhost")
    if url.port != EXPECTED_PORT:
        errors.append(f"host port mora biti {EXPECTED_PORT}")
    if url.query:
        errors.append("URL query parametri nisu dopusteni")
    if errors:
        raise UnsafeTestDatabaseError(
            "Odbijena nesigurna testna baza: " + "; ".join(errors)
        )
    return value


def configured_test_database_url(*, required: bool = False) -> str | None:
    """Vrati samo eksplicitni testni URL; u obaveznom nacinu fail-closed."""
    value = os.getenv("TEST_DATABASE_URL")
    if value is None and not required:
        return None
    return validate_test_database_url(value)


def validate_connected_identity(identity: DatabaseIdentity) -> None:
    """Ponovno provjeri stvarni server prije migracije ili testnog upisa."""
    errors = []
    if identity.database != EXPECTED_DATABASE:
        errors.append(f"spojena baza nije {EXPECTED_DATABASE}")
    if identity.user != EXPECTED_USER:
        errors.append(f"spojeni korisnik nije {EXPECTED_USER}")
    if identity.port != 5432:
        errors.append("interni PostgreSQL port nije 5432")
    if identity.server_version_num < MIN_POSTGRES_VERSION:
        errors.append("potreban je PostgreSQL 16 ili noviji")
    if identity.cluster_name != EXPECTED_CLUSTER_NAME:
        errors.append(f"cluster_name mora biti {EXPECTED_CLUSTER_NAME}")
    if errors:
        raise UnsafeTestDatabaseError(
            "Odbijen spoj na neocekivani PostgreSQL: " + "; ".join(errors)
        )


def _identity_from_row(row) -> DatabaseIdentity:
    return DatabaseIdentity(
        database=row[0],
        user=row[1],
        port=row[2],
        server_version_num=row[3],
        cluster_name=row[4],
    )


def inspect_migration_connection(connection: Connection) -> DatabaseIdentity:
    """Provjeri identitet na istoj sinkronoj konekciji koju koristi Alembic."""
    identity = _identity_from_row(connection.execute(IDENTITY_QUERY).one())
    validate_connected_identity(identity)
    return identity


def run_test_migration_transaction(
    connection: Connection,
    migration_operation: Callable[[Connection], None],
) -> None:
    """Provjeri identitet i migriraj atomarno na istoj konekciji."""
    with connection.begin():
        inspect_migration_connection(connection)
        migration_operation(connection)


async def inspect_test_database(value: str | None) -> DatabaseIdentity:
    """Spoji se read-only upitom i potvrdi identitet namjenske baze."""
    url = validate_test_database_url(value)
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            row = (await connection.execute(IDENTITY_QUERY)).one()
        identity = _identity_from_row(row)
        validate_connected_identity(identity)
        return identity
    finally:
        await engine.dispose()
