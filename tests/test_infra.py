"""The database container is configured the way the grader assumes.

Verdicts depend on these facts, so a wrong image or a dropped setting must
fail loudly here rather than silently change results later.
"""

import psycopg
import pytest


@pytest.fixture
def conn():
    with psycopg.connect(autocommit=True) as c:
        yield c


def setting(conn, name: str) -> str:
    return conn.execute("SELECT current_setting(%s)", (name,)).fetchone()[0]


def test_postgres_is_pinned_16_15(conn):
    assert setting(conn, "server_version_num") == "160015"


@pytest.mark.parametrize(
    "name, expected",
    [
        ("deadlock_timeout", "50ms"),
        ("autovacuum", "off"),
        ("fsync", "off"),
        ("synchronous_commit", "off"),
        ("full_page_writes", "off"),
    ],
)
def test_server_setting(conn, name, expected):
    assert setting(conn, name) == expected


def test_btree_gist_is_installable(conn):
    rows = conn.execute(
        "SELECT 1 FROM pg_available_extensions WHERE name = 'btree_gist'"
    ).fetchall()
    assert rows == [(1,)]


def test_default_isolation_is_read_committed(conn):
    assert setting(conn, "default_transaction_isolation") == "read committed"
