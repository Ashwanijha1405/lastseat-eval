"""Deterministic interleaving explorer (SPEC §5).

Each concurrent request runs in its own thread with its own connection. Every
`db` call pauses the thread until the scheduler grants it, so the scheduler
alone decides the order in which statements reach Postgres. After each grant
the scheduler waits for *quiescence*: every request is READY (paused at its
next step), DONE, or BLOCKED on a row/table lock that only another request's
future step can release. Lock waits are read from Postgres with
`pg_blocking_pids`, never inferred from timing.

A schedule is the list of choices made at each choice point (a moment when
two or more requests are READY). `Explorer.explore` enumerates all of them by
stateless depth-first search: every schedule runs on a fresh clone of a
template database, replaying a prefix of choices and then always taking the
lowest-numbered READY request.
"""

from __future__ import annotations

import random
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Sequence

import psycopg
from psycopg import sql as pgsql
from psycopg.pq import TransactionStatus

from .db_api import Db, Outcome, connect

POLL_S = 0.002
JOIN_TIMEOUT_S = 2.0

Request = Callable[[Db], Any]
Choice = tuple[tuple[int, ...], int]  # (READY requests, the one chosen)


class State(Enum):
    READY = "ready"
    RUNNING = "running"
    DONE = "done"


class StepLimitExceeded(BaseException):
    """Raised inside a request that took too many steps.

    A BaseException, so `except Exception` retry loops in model code cannot
    swallow it.
    """


class ScheduleAborted(BaseException):
    """Raised inside a request when the harness abandons the schedule."""


@dataclass(frozen=True)
class Invariant:
    name: str
    sql: str  # must return exactly one row with one boolean; true = holds
    # "safety": a rule that must hold however requests interleave.
    # "success": evidence that valid requests really took effect (liveness).
    kind: str = "safety"


@dataclass(frozen=True)
class InvariantResult:
    name: str
    holds: bool
    got: str
    kind: str = "safety"


@dataclass(frozen=True)
class RequestOutcome:
    kind: str  # "returned" | "raised" | "step_limit" | "aborted"
    value: Any
    text: str
    fingerprint: str


@dataclass(frozen=True)
class _Event:
    window: int  # number of the most recently granted step when this happened
    request: int
    step: int | None  # step this event completes; None for notes
    outcome: Outcome


@dataclass
class ScheduleResult:
    choices: tuple[int, ...]
    choice_points: tuple[Choice, ...]
    grants: tuple[tuple[int, int, str], ...]  # (step, request, label)
    events: tuple[_Event, ...]
    blocked: dict[int, dict[int, tuple[int, ...]]]  # step -> {request: blocking requests}
    outcomes: tuple[RequestOutcome, ...]
    invariants: tuple[InvariantResult, ...]
    # "ok" | "model_hang" (request code ran without returning or calling db)
    # | "harness_timeout" (stuck inside a statement) | "nondeterministic"
    status: str
    warnings: tuple[str, ...]
    reproduced: bool | None = None

    @property
    def invariants_hold(self) -> bool:
        """All safety invariants hold."""
        return self.status == "ok" and all(i.holds for i in self.invariants if i.kind == "safety")

    @property
    def success_holds(self) -> bool:
        """All success checks hold."""
        return self.status == "ok" and all(i.holds for i in self.invariants if i.kind == "success")

    def trace(self) -> str:
        return self._render(lambda o: o.text, labels=True)

    def fingerprint(self) -> str:
        """What must match when the schedule is re-run, ignoring row values."""
        return f"{self.choice_points}|{self.status}\n" + self._render(lambda o: o.kind, labels=False)

    def _render(self, show: Callable[[Outcome], str], labels: bool) -> str:
        by_window: dict[int, list[_Event]] = defaultdict(list)
        for e in self.events:
            by_window[e.window].append(e)  # per-request order is program order

        lines = [f"schedule choices: {list(self.choices)}"]

        def notes(window: int, first: int | None, skip: _Event | None) -> None:
            events = by_window.get(window, [])
            order = sorted({e.request for e in events}, key=lambda r: (r != first, r))
            for r in order:
                for e in events:
                    if e.request != r or e is skip:
                        continue
                    resumed = f"step {e.step} resumed -> " if e.step is not None else ""
                    lines.append(f"{'':9}{_r(r)}  {resumed}{show(e.outcome)}")

        notes(0, None, None)
        for step, req, label in self.grants:
            own = next((e for e in by_window.get(step, []) if e.step == step), None)
            head = f"step {step:<4}{_r(req)}  {label if labels else ''}"
            if own is not None:
                head += f" -> {show(own.outcome)}"
            else:
                blockers = self.blocked.get(step, {}).get(req, ())
                head += f" -> blocked (waiting for {', '.join(map(_r, blockers)) or '?'})"
            lines.append(head)
            notes(step, req, own)

        for inv in self.invariants:
            ok, bad = ("invariant ok", "INVARIANT VIOLATED") if inv.kind == "safety" else (
                "success check ok", "SUCCESS CHECK FAILED")
            lines.append(f"{ok}: {inv.name}" if inv.holds else f"{bad}: {inv.name}  (got {inv.got})")
        if self.status != "ok":
            lines.append(f"SCHEDULE {self.status.upper()}")
        lines.extend(f"warning: {w}" for w in self.warnings)
        return "\n".join(lines) + "\n"


@dataclass
class Exploration:
    results: list[ScheduleResult]
    exhaustive: bool
    dfs_schedules: int
    random_seed: int | None
    failures: list[ScheduleResult] = field(default_factory=list)
    harness_error: ScheduleResult | None = None

    @property
    def all_reproduced(self) -> bool:
        return all(r.reproduced for r in self.failures)


def _r(index: int) -> str:
    return f"R{index + 1}"


class _Run:
    """State shared between the scheduler and the request threads of one schedule."""

    def __init__(self, step_limit: int) -> None:
        self.cond = threading.Condition()
        self.version = 0  # bumped on every state change the scheduler cares about
        self.step_no = 0
        self.aborting = False
        self.step_limit = step_limit
        self.events: list[_Event] = []
        self.grants: list[tuple[int, int, str]] = []
        self.blocked: dict[int, dict[int, tuple[int, ...]]] = {}
        self.warnings: list[str] = []

    def record(self, request: int, step: int | None, outcome: Outcome) -> None:
        """Call with `cond` held."""
        self.events.append(_Event(self.step_no, request, step, outcome))
        self.version += 1
        self.cond.notify_all()


class _Worker:
    """One concurrent request: a thread running the request function. Acts as
    the `Hooks` of its `Db`, so every db call passes through `before`."""

    def __init__(self, index: int, fn: Request, conn: psycopg.Connection, run: _Run) -> None:
        self.index = index
        self.fn = fn
        self.conn = conn
        self.run = run
        self.pid = conn.info.backend_pid
        self.state = State.RUNNING
        self.pending = ""
        self.granted = False
        self.in_statement = False  # granted and not yet finished
        self.step: int | None = None
        self.steps_taken = 0
        self.hit_step_limit = False
        self.outcome: RequestOutcome | None = None
        self.thread = threading.Thread(target=self._main, name=f"lastseat-{_r(index)}", daemon=True)

    def before(self, label: str) -> None:
        run = self.run
        with run.cond:
            if run.aborting:
                raise ScheduleAborted()
            if self.steps_taken >= run.step_limit:
                self.hit_step_limit = True
                raise StepLimitExceeded()
            self.steps_taken += 1
            self.pending = label
            self.state = State.READY
            run.version += 1
            run.cond.notify_all()
            run.cond.wait_for(lambda: self.granted or run.aborting)
            if not self.granted:
                raise ScheduleAborted()
            self.granted = False
            self.in_statement = True

    def after(self, outcome: Outcome) -> None:
        with self.run.cond:
            self.in_statement = False
            self.run.record(self.index, self.step, outcome)

    def _main(self) -> None:
        try:
            value = self.fn(Db(self.conn, hooks=self))
            outcome = _returned(value)
        except StepLimitExceeded:
            outcome = _step_limit(self.run.step_limit)
        except ScheduleAborted:
            outcome = RequestOutcome("aborted", None, "aborted by harness", "aborted")
        except BaseException as e:
            outcome = _raised(e)
        if self.hit_step_limit and outcome.kind != "aborted":
            outcome = _step_limit(self.run.step_limit)
        self._close_open_transaction()
        with self.run.cond:
            self.run.record(self.index, None, Outcome(outcome.text, outcome.fingerprint))
            self.outcome = outcome
            self.state = State.DONE

    def _close_open_transaction(self) -> None:
        try:
            if self.conn.info.transaction_status == TransactionStatus.IDLE:
                return
            self.conn.execute("ROLLBACK")
        except psycopg.Error:
            return  # connection already gone (e.g. terminated after a timeout)
        with self.run.cond:
            note = "function ended inside an open transaction; harness rolled it back"
            self.run.record(self.index, None, Outcome(note, "harness rollback"))
            self.run.warnings.append(f"{_r(self.index)}: {note}")


def _returned(value: Any) -> RequestOutcome:
    if value is None or isinstance(value, bool):
        fp = f"returned {value!r}"
    else:
        fp = f"returned {type(value).__name__}"
    return RequestOutcome("returned", value, f"returned {value!r}", fp)


def _raised(e: BaseException) -> RequestOutcome:
    sqlstate = getattr(e, "sqlstate", None)
    code = f" ({sqlstate})" if sqlstate else ""
    first_line = str(e).strip().splitlines()[0] if str(e).strip() else ""
    return RequestOutcome(
        "raised", e, f"raised {type(e).__name__}{code}: {first_line}", f"raised {type(e).__name__}{code}"
    )


def _step_limit(limit: int) -> RequestOutcome:
    return RequestOutcome("step_limit", None, f"hit the step limit ({limit} steps)", "step_limit")


def _has_cycle(waits: dict[int, list[int]]) -> bool:
    """True if the waits-for graph among `waits`' keys has a cycle (a deadlock
    Postgres has not resolved yet)."""
    finished: set[int] = set()
    on_path: set[int] = set()

    def visit(p: int) -> bool:
        if p in on_path:
            return True
        if p in finished or p not in waits:
            return False
        on_path.add(p)
        found = any(visit(q) for q in waits[p])
        on_path.discard(p)
        finished.add(p)
        return found

    return any(visit(p) for p in waits)


def _next_prefix(points: Sequence[Choice]) -> tuple[int, ...] | None:
    """The next schedule in depth-first order: change the deepest choice point
    that still has an untried higher alternative. None when all are tried."""
    for i in range(len(points) - 1, -1, -1):
        ready, chosen = points[i]
        higher = [r for r in ready if r > chosen]
        if higher:
            return tuple(c for _, c in points[:i]) + (higher[0],)
    return None


def _recreate_database(
    admin: psycopg.Connection, name: str, template: str | None = None, owner: str | None = None
) -> None:
    admin.execute(pgsql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(pgsql.Identifier(name)))
    query = pgsql.SQL("CREATE DATABASE {}").format(pgsql.Identifier(name))
    if template is not None:
        query += pgsql.SQL(" TEMPLATE {} STRATEGY FILE_COPY").format(pgsql.Identifier(template))
    if owner is not None:
        query += pgsql.SQL(" OWNER {}").format(pgsql.Identifier(owner))
    admin.execute(query)


def ensure_role(role: str, conninfo: str = "") -> None:
    """Create a non-superuser login role (password = role name) if missing.

    Model code runs as this role, so it cannot change server settings such as
    deadlock_timeout or run programs on the db host. It owns each test
    database, so it can still create tables, constraints, triggers and
    trusted extensions such as btree_gist.
    """
    with psycopg.connect(conninfo, autocommit=True) as admin:
        if admin.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone():
            return
        admin.execute("SET scram_iterations = 1")  # fast logins; throwaway password
        admin.execute(
            pgsql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(pgsql.Identifier(role), pgsql.Literal(role))
        )


def build_template(
    name: str,
    setup_sql: str,
    *,
    seed_sql: str | None = None,
    migrate: Callable[[Db], Any] | None = None,
    role: str | None = None,
    conninfo: str = "",
) -> None:
    """Create database `name`: schema, then optional migrate(db), then seed rows.

    Every schedule starts from a byte-for-byte copy of it (SPEC §5.6). With
    `role`, the database is owned by that role and all three steps run as it.
    """
    with psycopg.connect(conninfo, autocommit=True) as admin:
        _recreate_database(admin, name, owner=role)
    with connect(name, conninfo, role) as conn:
        if setup_sql.strip():
            conn.execute(setup_sql)
        if migrate is not None:
            migrate(Db(conn))
        if seed_sql:
            conn.execute(seed_sql)


def drop_database(name: str, conninfo: str = "") -> None:
    with psycopg.connect(conninfo, autocommit=True) as admin:
        admin.execute(pgsql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(pgsql.Identifier(name)))


class Explorer:
    """Runs one set of concurrent requests against clones of a template database."""

    def __init__(
        self,
        template: str,
        requests: Sequence[Request],
        invariants: Sequence[Invariant],
        *,
        step_limit: int = 60,
        schedule_timeout_s: float = 15.0,
        role: str | None = None,
        conninfo: str = "",
    ) -> None:
        self.template = template
        self.run_db = f"{template}_run"
        self.requests = list(requests)
        self.invariants = list(invariants)
        self.step_limit = step_limit
        self.schedule_timeout_s = schedule_timeout_s
        self.role = role  # requests connect as this role; invariants run as admin
        self.conninfo = conninfo
        # Creates/drops the per-schedule databases and doubles as the lock monitor.
        self._admin = psycopg.connect(conninfo, autocommit=True)

    def close(self) -> None:
        try:
            self._admin.execute(
                pgsql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(pgsql.Identifier(self.run_db))
            )
        finally:
            self._admin.close()

    def __enter__(self) -> Explorer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def explore(
        self,
        *,
        max_schedules: int = 2000,
        random_schedules: int = 200,
        seed: int = 0,
        is_failure: Callable[[ScheduleResult], bool] | None = None,
    ) -> Exploration:
        """Run every schedule (up to `max_schedules`), then seeded-random ones
        if the tree was too big, then re-run each failing schedule once."""
        is_failure = is_failure or (lambda r: not r.invariants_hold)
        results: list[ScheduleResult] = []
        prefix: tuple[int, ...] | None = ()
        while prefix is not None and len(results) < max_schedules:
            r = self.run(prefix)
            results.append(r)
            if r.status != "ok":
                return Exploration(results, False, len(results), None, harness_error=r)
            prefix = _next_prefix(r.choice_points)
        exhaustive = prefix is None
        dfs_schedules = len(results)

        random_seed = None
        if not exhaustive and random_schedules > 0:
            random_seed = seed
            for i in range(random_schedules):
                r = self.run(rng=random.Random(f"{seed}:{i}"))
                results.append(r)
                if r.status != "ok":
                    return Exploration(results, False, dfs_schedules, random_seed, harness_error=r)

        failures = [r for r in results if is_failure(r)]
        for r in failures:
            r.reproduced = self.run(r.choices).fingerprint() == r.fingerprint()
        return Exploration(results, exhaustive, dfs_schedules, random_seed, failures)

    def run(self, prefix: Sequence[int] = (), rng: random.Random | None = None) -> ScheduleResult:
        """Run one schedule on a fresh database.

        At the i-th choice point take `prefix[i]`; past the prefix take a
        random READY request if `rng` is given, else the lowest-numbered one.
        """
        _recreate_database(self._admin, self.run_db, self.template, owner=self.role)
        run = _Run(self.step_limit)
        conns: list[psycopg.Connection] = []
        try:
            conns = [connect(self.run_db, self.conninfo, self.role) for _ in self.requests]
            workers = [_Worker(i, fn, c, run) for i, (fn, c) in enumerate(zip(self.requests, conns))]
            status, points = self._drive(run, workers, tuple(prefix), rng)
            invariants = self._check_invariants() if status == "ok" else ()
        finally:
            for c in conns:
                c.close()
            self._admin.execute(
                pgsql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(pgsql.Identifier(self.run_db))
            )
        return ScheduleResult(
            choices=tuple(c for _, c in points),
            choice_points=tuple(points),
            grants=tuple(run.grants),
            events=tuple(run.events),
            blocked=run.blocked,
            outcomes=tuple(
                w.outcome or RequestOutcome("aborted", None, "aborted by harness", "aborted") for w in workers
            ),
            invariants=tuple(invariants),
            status=status,
            warnings=tuple(run.warnings),
        )

    def _drive(
        self, run: _Run, workers: list[_Worker], prefix: tuple[int, ...], rng: random.Random | None
    ) -> tuple[str, list[Choice]]:
        deadline = time.monotonic() + self.schedule_timeout_s
        points: list[Choice] = []
        status = "ok"
        for w in workers:
            w.thread.start()
        try:
            while True:
                if not self._wait_quiescent(run, workers, deadline):
                    with run.cond:
                        spinning = any(w.state is State.RUNNING and not w.in_statement for w in workers)
                    status = "model_hang" if spinning else "harness_timeout"
                    break
                ready = tuple(w.index for w in workers if w.state is State.READY)
                if not ready:
                    break  # quiescent with nobody READY means everyone is DONE
                if len(ready) == 1:
                    pick = ready[0]
                else:
                    depth = len(points)
                    if depth < len(prefix):
                        pick = prefix[depth]
                        if pick not in ready:
                            status = "nondeterministic"
                            break
                    elif rng is not None:
                        pick = rng.choice(ready)
                    else:
                        pick = ready[0]
                    points.append((ready, pick))
                self._grant(run, workers[pick])
        except BaseException:
            status = "harness_error"
            raise
        finally:
            if status != "ok":
                self._abort(run, workers)
            for w in workers:
                w.thread.join(timeout=JOIN_TIMEOUT_S)
                if w.thread.is_alive():
                    run.warnings.append(f"{_r(w.index)}: thread did not stop (still running Python code)")
        return status, points

    def _grant(self, run: _Run, w: _Worker) -> None:
        with run.cond:
            run.step_no += 1
            w.step = run.step_no
            run.grants.append((run.step_no, w.index, w.pending))
            w.state = State.RUNNING
            w.granted = True
            run.version += 1
            run.cond.notify_all()

    def _wait_quiescent(self, run: _Run, workers: list[_Worker], deadline: float) -> bool:
        """Wait until no request can progress without the scheduler.

        Quiescent means: every request is READY, DONE, or BLOCKED on a lock,
        at least one is READY (unless all are DONE), and the blocked ones do
        not wait on each other in a cycle. A cycle is a deadlock that Postgres
        breaks by itself after deadlock_timeout, so we wait for that rather
        than race it.
        """
        while time.monotonic() < deadline:
            with run.cond:
                run.cond.wait_for(lambda: all(w.state is not State.RUNNING for w in workers), timeout=POLL_S)
                version = run.version
                running = [w for w in workers if w.state is State.RUNNING]
                any_ready = any(w.state is State.READY for w in workers)
            if not running:
                return True
            if not any_ready:
                continue  # everyone still working or in a deadlock: keep waiting
            waits = self._lock_waits([w.pid for w in running])
            with run.cond:
                if run.version != version:
                    continue  # something moved while we were asking Postgres
                if all(waits.get(w.pid) for w in running) and not _has_cycle(waits):
                    index_of = {w.pid: w.index for w in workers}
                    run.blocked[run.step_no] = {
                        w.index: tuple(sorted(index_of[p] for p in waits[w.pid] if p in index_of))
                        for w in running
                    }
                    return True
                run.cond.wait(timeout=POLL_S)
        return False

    def _lock_waits(self, pids: list[int]) -> dict[int, list[int]]:
        rows = self._admin.execute(
            "SELECT pid, pg_blocking_pids(pid) FROM unnest(%s::int[]) AS pid", (pids,)
        ).fetchall()
        return {pid: blockers for pid, blockers in rows}

    def _abort(self, run: _Run, workers: list[_Worker]) -> None:
        with run.cond:
            run.aborting = True
            run.cond.notify_all()
        for w in workers:
            if w.state is State.RUNNING:
                try:
                    self._admin.execute("SELECT pg_terminate_backend(%s)", (w.pid,))
                except psycopg.Error:
                    pass

    def _check_invariants(self) -> list[InvariantResult]:
        results = []
        with connect(self.run_db, self.conninfo) as conn:
            for inv in self.invariants:
                try:
                    rows = conn.execute(inv.sql).fetchall()
                    results.append(InvariantResult(inv.name, rows == [(True,)], repr(rows), inv.kind))
                except psycopg.Error as e:
                    got = f"ERROR {e.sqlstate}: {e.diag.message_primary}"
                    results.append(InvariantResult(inv.name, False, got, inv.kind))
        return results
