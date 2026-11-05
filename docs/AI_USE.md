# AI use log

What each Claude Code session drafted, and what the human reviewed or changed.
Newest entries at the bottom.

---

## M0: skeleton and infrastructure (2026-11-06, Claude Code / Claude Opus 5.5)

**Drafted by Claude**
- `docker-compose.yml`: `db` = `postgres:16.15-bookworm` on tmpfs with
  `deadlock_timeout=50ms`, `autovacuum=off`, `fsync/synchronous_commit/
  full_page_writes=off`; `eval` = local Python image, repo bind-mounted at
  `/app`, `.env` loaded at runtime only if present.
- `Dockerfile` (`python:3.12.16-slim-bookworm`), `requirements.txt` (direct +
  transitive pins from `pip freeze`), `pytest.ini`.
- `Makefile` with `help/up/down/build/test/psql/shell`. Later targets
  (`validate`, `pilot`, `run`, `report`, `zip`) are added in their milestones.
- `.gitignore` and `.dockerignore` (both exclude `.env`), `.env.example`.
- `tests/test_infra.py`: asserts Postgres version 160015, the five server
  settings, `btree_gist` availability, default isolation = read committed.
- `CLAUDE.md` (working rules), this file.

**Verified by Claude**
- `make build && make test`: 8/8 pass.
- Overriding `deadlock_timeout=1s` via `PGOPTIONS` makes the matching test
  fail (the test detects a wrong setting).
- A dummy `.env` shows as ignored in `git status --ignored`, is absent from
  the built image, and is visible as an env var in the container at runtime.

**Human to review**
- Version choices: psycopg 3.3.6 (not 3.3.8, which shipped a day after 3.3.7
  and looks like a hotfix), pytest 9.1.1, Postgres 16.15.
- Whether the durability-off settings are acceptable (argued: they affect
  crash safety only, not locking/MVCC/SSI semantics).
- Hardcoded throwaway db password `lastseat` in compose (port not published).

---

## M1: `db` API, scheduler, scheduler tests (2026-11-06, Claude Code / Claude Opus 5.5)

**Drafted by Claude**
- `lastseat/db_api.py`: `Db` with `begin/execute/commit/rollback`; each call
  is a step routed through `hooks.before/after`. `connect()` sets autocommit
  and `prepare_threshold=None`.
- `lastseat/scheduler.py`: request threads, quiescence via
  `pg_blocking_pids` plus waits-for cycle check, stateless DFS with
  prefix replay, seeded-random fallback past `max_schedules`, step limit,
  harness timeout, template clone per schedule (`STRATEGY FILE_COPY`),
  readable traces, fingerprints for reproduction checks.
- `tests/conftest.py`, `tests/test_scheduler.py` (17 tests).

**Design decisions beyond the literal spec (human to confirm)**
1. *One statement per `execute()`*, enforced by sending through psycopg
   pipeline mode (extended protocol). Without it `"a; b"` with no params runs
   as one atomic step and hides interleavings.
2. *Autocommit statements get a separate commit step*
   (`BEGIN; stmt; <step>; COMMIT`). Spec §4/§5.1 read literally make an
   autocommit `execute` one step. Mutation check: with the literal version,
   the single-statement subquery lost update is missed (2 schedules, 0
   failures); with the extra step it is caught. This only adds
   interleavings that real Postgres allows.
3. *Reproduction compares a fingerprint* (request per step, status/sqlstate,
   blocked-on, invariant results, outcome kinds), not raw row values, so
   `now()`-style values don't count as nondeterminism. Tests also assert
   byte-identical trace text for the toy programs.

**Verified by Claude**
- `make test`: 25 passed (~28 s). Lost update: 40/50 schedules fail, all
  reproduce. `UPDATE n=n+1` and `SELECT … FOR UPDATE`: 0 failures, blocking
  observed. Interleaving counts match C(6,3)=20 and 6!/(2!2!2!)=90.
- Deadlock: first waiter is the victim; same victim on 5 replays.
- Reset cost measured: clone 7 ms (`FILE_COPY`) vs 9.5 ms (`WAL_LOG`);
  ~28 ms per schedule end to end (~70 ms when a deadlock is involved).

**Known limitations to resolve later**
- Interleaving is per statement: a PL/pgSQL function or DO block that runs
  several statements internally is one step.
- Deadlock victim depends on the second waiter joining the cycle within
  `deadlock_timeout` (50 ms); steps take a few ms, and the per-failure
  `reproduced` flag would expose a flip.
- Model code currently connects as the superuser and can reach `db._conn`;
  M2 sandbox should use a non-superuser role and run grading in a
  subprocess (a pure-Python infinite loop leaks a thread today).

**Human to review**
- The three design decisions above; whether to amend SPEC §4/§5.1 to match.
- Trace format (examples in the M1 hand-off message).
