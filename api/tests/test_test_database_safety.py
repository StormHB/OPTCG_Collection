"""Unit testovi fail-closed zastite PostgreSQL testne baze."""

import pytest

from app.core.test_database import (
    IDENTITY_QUERY,
    DatabaseIdentity,
    UnsafeTestDatabaseError,
    configured_test_database_url,
    inspect_migration_connection,
    run_test_migration_transaction,
    validate_connected_identity,
    validate_test_database_url,
)

VALID_URL = "postgresql+asyncpg://optcg_test_user:password@127.0.0.1:5434/optcg_test"


def test_exact_test_database_url_is_accepted():
    assert validate_test_database_url(VALID_URL) == VALID_URL


def test_required_postgres_mode_rejects_missing_url(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(UnsafeTestDatabaseError, match="mora biti izricito postavljen"):
        configured_test_database_url(required=True)


@pytest.mark.parametrize(
    "query",
    [
        "port=5433",
        "host=localhost",
        "database=optcg",
        "user=optcg_user",
        "ssl=require",
        "application_name=optcg_test",
    ],
)
def test_all_url_query_parameters_are_rejected(query):
    with pytest.raises(UnsafeTestDatabaseError, match="query parametri"):
        validate_test_database_url(f"{VALID_URL}?{query}")


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "postgresql+asyncpg://optcg_user:password@127.0.0.1:5433/optcg",
        "postgresql+asyncpg://optcg_test_user:password@127.0.0.1:5434/optcg",
        "postgresql+asyncpg://optcg_user:password@127.0.0.1:5434/optcg_test",
        "postgresql+asyncpg://optcg_test_user:password@db:5434/optcg_test",
        "postgresql://optcg_test_user:password@127.0.0.1:5434/optcg_test",
    ],
)
def test_missing_or_development_database_configuration_is_rejected(value):
    with pytest.raises(UnsafeTestDatabaseError):
        validate_test_database_url(value)


def test_connected_database_identity_is_checked_independently_of_url():
    with pytest.raises(UnsafeTestDatabaseError, match="spojena baza"):
        validate_connected_identity(
            DatabaseIdentity(
                database="optcg",
                user="optcg_test_user",
                port=5432,
                server_version_num=160000,
                cluster_name="optcg_test_11c",
            )
        )


def test_connected_database_rejects_wrong_cluster_name():
    with pytest.raises(UnsafeTestDatabaseError, match="cluster_name"):
        validate_connected_identity(
            DatabaseIdentity(
                database="optcg_test",
                user="optcg_test_user",
                port=5432,
                server_version_num=160000,
                cluster_name="main",
            )
        )


def test_migration_identity_is_checked_on_supplied_connection():
    expected = (
        "optcg_test",
        "optcg_test_user",
        5432,
        160000,
        "optcg_test_11c",
    )

    class Result:
        def one(self):
            return expected

    class Connection:
        def __init__(self):
            self.statement = None

        def execute(self, statement):
            self.statement = statement
            return Result()

    connection = Connection()
    identity = inspect_migration_connection(connection)

    assert connection.statement is IDENTITY_QUERY
    assert identity.cluster_name == "optcg_test_11c"


class _Transaction:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        if exception_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False


class _MigrationConnection:
    def __init__(self, *, cluster_name="optcg_test_11c"):
        self.cluster_name = cluster_name
        self.transaction = _Transaction()
        self.events = []

    def begin(self):
        self.events.append("begin")
        return self.transaction

    def execute(self, statement):
        assert statement is IDENTITY_QUERY
        self.events.append("identity")

        class Result:
            def __init__(self, cluster_name):
                self.cluster_name = cluster_name

            def one(self):
                return (
                    "optcg_test",
                    "optcg_test_user",
                    5432,
                    160000,
                    self.cluster_name,
                )

        return Result(self.cluster_name)


def test_successful_test_migration_uses_same_connection_and_commits():
    connection = _MigrationConnection()

    def migrate(received_connection):
        assert received_connection is connection
        connection.events.append("migrate")

    run_test_migration_transaction(connection, migrate)

    assert connection.events == ["begin", "identity", "migrate"]
    assert connection.transaction.committed is True
    assert connection.transaction.rolled_back is False


def test_test_migration_exception_rolls_back():
    connection = _MigrationConnection()

    def fail(_connection):
        connection.events.append("migrate")
        raise RuntimeError("migration failed")

    with pytest.raises(RuntimeError, match="migration failed"):
        run_test_migration_transaction(connection, fail)

    assert connection.events == ["begin", "identity", "migrate"]
    assert connection.transaction.committed is False
    assert connection.transaction.rolled_back is True


def test_invalid_identity_rolls_back_before_migration_operation():
    connection = _MigrationConnection(cluster_name="main")
    migration_called = False

    def migrate(_connection):
        nonlocal migration_called
        migration_called = True

    with pytest.raises(UnsafeTestDatabaseError, match="cluster_name"):
        run_test_migration_transaction(connection, migrate)

    assert migration_called is False
    assert connection.events == ["begin", "identity"]
    assert connection.transaction.committed is False
    assert connection.transaction.rolled_back is True
