"""Low-level PostgreSQL connection factory."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.settings import settings

_pool: ConnectionPool | None = None


def _database_url() -> str:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required. SQLite is no longer supported.")
    return settings.database_url


def _convert_placeholders(query: str) -> str:
    """Keep existing repository SQL readable while executing through psycopg."""
    return query.replace("?", "%s")


class PostgresCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query: str, params: Sequence[Any] | None = None):
        return self._cursor.execute(_convert_placeholders(query), params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class PostgresConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, query: str, params: Sequence[Any] | None = None):
        return self._connection.execute(_convert_placeholders(query), params)

    def cursor(self) -> PostgresCursor:
        return PostgresCursor(self._connection.cursor())

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()


def _create_pool() -> ConnectionPool:
    pool = ConnectionPool(
        conninfo=_database_url(),
        min_size=0,
        max_size=10,
        timeout=10,
        reconnect_timeout=10,
        kwargs={"row_factory": dict_row, "connect_timeout": 10},
        open=False,
    )
    pool.open(wait=False)
    return pool


def _pool_instance() -> ConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = _create_pool()
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None and not _pool.closed:
        _pool.close()
    _pool = None


@contextmanager
def get_connection() -> Iterator[PostgresConnection]:
    """Return a PostgreSQL connection from the process pool."""
    with _pool_instance().connection() as connection:
        yield PostgresConnection(connection)


def _advisory_key(name: str) -> int:
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


def advisory_xact_lock(connection: PostgresConnection, name: str) -> None:
    """Serialize related writes for the duration of the current transaction."""
    connection.execute("SELECT pg_advisory_xact_lock(%s)", (_advisory_key(name),))


@contextmanager
def advisory_lock(name: str) -> Iterator[None]:
    """Hold a PostgreSQL advisory lock while nested repository work executes."""
    with get_connection() as connection:
        advisory_xact_lock(connection, name)
        yield
        connection.commit()
