"""The `db` object that model-written code receives.

Each concurrent request gets its own `Db` wrapping its own connection. Every
public method is one *step*: before it touches Postgres, `Db` calls
`hooks.before(label)`, which the scheduler uses to pause the request until it
is that request's turn. When the step finishes, `hooks.after(outcome)` records
what happened. Without hooks (solo checks, `migrate`) nothing pauses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import psycopg
from psycopg.pq import TransactionStatus

ISOLATION_LEVELS = {
    "read committed": "READ COMMITTED",
    "repeatable read": "REPEATABLE READ",
    "serializable": "SERIALIZABLE",
}

# Statements that manage the transaction themselves (or cannot run inside one),
# so they are sent as-is instead of being wrapped in an implicit transaction.
_NO_IMPLICIT_TX = re.compile(
    r"\s*(?:(?:--[^\n]*(?:\n|$)|/\*.*?\*/)\s*)*"
    r"(?:BEGIN|START|COMMIT|END|ROLLBACK|ABORT|SAVEPOINT|RELEASE|PREPARE|VACUUM)\b",
    re.IGNORECASE | re.DOTALL,
)

MAX_ROWS_SHOWN = 5


@dataclass(frozen=True)
class Outcome:
    """What one step did.

    `text` goes into human-readable traces. `kind` leaves out row values, so
    two runs of the same schedule can be compared even when values such as
    now() legitimately differ.
    """

    text: str
    kind: str


class Hooks(Protocol):
    def before(self, label: str) -> None: ...
    def after(self, outcome: Outcome) -> None: ...


class _NoHooks:
    def before(self, label: str) -> None:
        pass

    def after(self, outcome: Outcome) -> None:
        pass


def connect(dbname: str, conninfo: str = "") -> psycopg.Connection:
    """Open a connection the way every harness connection is opened.

    Autocommit, because `begin()` sends an explicit BEGIN. No automatic
    server-side prepared statements, so statement 6 behaves like statement 1.
    """
    return psycopg.connect(conninfo, dbname=dbname, autocommit=True, prepare_threshold=None)


class Db:
    def __init__(self, conn: psycopg.Connection, hooks: Hooks | None = None) -> None:
        self._conn = conn
        self._hooks = hooks or _NoHooks()

    def begin(self, isolation: str = "read committed") -> None:
        level = ISOLATION_LEVELS.get(isolation.strip().lower()) if isinstance(isolation, str) else None
        if level is None:
            raise ValueError(f"isolation must be one of {sorted(ISOLATION_LEVELS)}, got {isolation!r}")
        self._step(f"BEGIN ISOLATION LEVEL {level}", None)

    def execute(self, sql: str, params: dict | tuple | list | None = None) -> list[tuple]:
        if not isinstance(sql, str):
            raise TypeError(f"sql must be a str, got {type(sql).__name__}")
        idle = self._conn.info.transaction_status == TransactionStatus.IDLE
        if idle and not _NO_IMPLICIT_TX.match(sql):
            return self._autocommit_step(sql, params)
        return self._step(sql, params)

    def commit(self) -> None:
        self._step("COMMIT", None)

    def rollback(self) -> None:
        self._step("ROLLBACK", None)

    def _step(self, sql: str, params, label: str | None = None) -> list[tuple]:
        self._hooks.before(label or _label(self._conn, sql, params))
        try:
            rows, status, has_rows = _send(self._conn, sql, params)
        except Exception as e:
            self._hooks.after(_error_outcome(e))
            raise
        self._hooks.after(_success_outcome(rows, status, has_rows))
        return rows

    def _autocommit_step(self, sql: str, params) -> list[tuple]:
        """Run a statement outside begin()/commit() as BEGIN; stmt; <step>; COMMIT.

        In real Postgres another request can act after an autocommit statement
        has run but before it has committed (its row locks are still held).
        Making that commit its own step lets the scheduler explore that window.
        """
        self._hooks.before(_label(self._conn, sql, params) + "   [autocommit]")
        try:
            _send(self._conn, "BEGIN", None)
            rows, status, has_rows = _send(self._conn, sql, params)
        except Exception as e:
            _rollback_quietly(self._conn)
            self._hooks.after(_error_outcome(e))
            raise
        self._hooks.after(_success_outcome(rows, status, has_rows))
        self._step("COMMIT", None, label="COMMIT   [autocommit]")
        return rows


def _send(conn: psycopg.Connection, sql: str, params) -> tuple[list[tuple], str, bool]:
    cur = conn.cursor()
    # Pipeline mode always uses the extended query protocol, which carries one
    # statement per message: Postgres rejects "a; b" before running either.
    with conn.pipeline():
        cur.execute(sql, params)
    has_rows = cur.description is not None
    rows = cur.fetchall() if has_rows else []
    return rows, cur.statusmessage or "", has_rows


def _rollback_quietly(conn: psycopg.Connection) -> None:
    try:
        conn.execute("ROLLBACK")
    except psycopg.Error:
        pass


def _label(conn: psycopg.Connection, sql: str, params) -> str:
    text = sql
    if params is not None:
        try:
            text = psycopg.ClientCursor(conn).mogrify(sql, params)
        except Exception:
            text = f"{sql}  -- params: {params!r}"
    return " ".join(text.split())


def _success_outcome(rows: list[tuple], status: str, has_rows: bool) -> Outcome:
    if not has_rows:
        return Outcome(status, status)
    shown = repr(rows[:MAX_ROWS_SHOWN])
    if len(rows) > MAX_ROWS_SHOWN:
        shown = f"{shown[:-1]}, ...] ({len(rows)} rows)"
    text = shown if status.startswith("SELECT") else f"{status} {shown}"
    return Outcome(text, status)


def _error_outcome(e: BaseException) -> Outcome:
    message = str(e).strip().splitlines()[0] if str(e).strip() else ""
    if isinstance(e, psycopg.Error):
        message = e.diag.message_primary or message
        if e.sqlstate:
            return Outcome(f"ERROR {e.sqlstate} {type(e).__name__}: {message}", f"error {e.sqlstate}")
    return Outcome(f"ERROR {type(e).__name__}: {message}", f"error {type(e).__name__}")
