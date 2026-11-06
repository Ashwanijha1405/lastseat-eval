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

---

## M2: task loader, grader, validation, t01 (2026-11-06, Claude Code / Claude Opus 5.5)

**Drafted by Claude**
- `lastseat/sandbox.py`: AST import allow-list (`forbidden_import`), guarded
  `__import__`, builtins without `open/eval/exec/compile/input`;
  `import psycopg` yields a view with only the exception classes.
- `lastseat/task.py`: strict `spec.yaml` loader (unknown keys rejected),
  per-scenario `invariants` added on top of task-wide ones.
- `lastseat/grade.py`: solo checks (one-request run + `expect_return` +
  `expect_sql`), scenario exploration, safety/solo/liveness scoring per
  §6.1, up to 3 distinct counterexamples, `migrate_error`; CLI and
  `grade_in_subprocess` (each grade in its own process).
- `lastseat/validate.py` + `make validate`: references must pass; wrong
  variants must fail exactly the components in their `EXPECT:` docstring
  line; failures must reproduce; policy checks (>=2 solo checks, both
  scenario kinds, >=2 wrong variants, `task.md` contains `setup.sql`).
  Writes `results/validation.md` and `results/validation/<task>/<variant>/`.
- `lastseat/prompts/contract.md` (model-facing API contract).
- Scheduler: requests run as non-superuser role `lastseat_app` (owns each
  test db); `model_hang` status when request code spins without calling db.
- `tasks/t01_flash_sale/`: task.md, setup.sql, spec.yaml, reference, four
  wrong variants (w1 lost update, w2 RR no retry, w3 check-then-decrement,
  w4 NOWAIT), NOTES.md.
- `tests/test_sandbox.py`, `tests/test_task.py`.

**Verified by Claude**
- `make test`: 50 passed. `make validate`: all checks passed, twice, same
  results; every counterexample reproduces.
- Validator bites: a wrong `EXPECT:` and a failing "reference" are both
  reported as problems. A spinning request → `model_hang` and the process
  exits.
- Role probe: `lastseat_app` can `CREATE EXTENSION btree_gist`; it cannot set
  `deadlock_timeout`, `ALTER SYSTEM`, or `COPY … TO PROGRAM`.

**Decisions beyond the literal spec (human to confirm)**
1. Per-scenario invariants (SPEC §6 example's conservation `= 5` breaks the
   6-stock scenario).
2. `import psycopg` allowed, bound to an exceptions-only view (spec lists
   only `psycopg.errors`); `__future__` allowed too.
3. `EXPECT:` line in each wrong variant, checked exactly by validate.
4. Step-limit hits count as liveness failures in every scenario, not only
   `must_all_succeed` ones (SPEC §5.4 "counts as liveness failure").
5. A scenario that stops with `model_hang` scores neither safe nor live.

**Human to review**
- `lastseat/prompts/contract.md` and `tasks/t01_flash_sale/task.md`: wording
  models will see; is every graded rule stated, and is no hazard named?
- The four counterexamples under `results/validation/t01_flash_sale/`.
- Open question: in safety-only scenarios a loser that *raises* (instead of
  returning False) is not penalised, matching SPEC. Stricter option: expect
  the multiset of returns, e.g. exactly one True and one False.

---

## M3 / t02 on-call rota (2026-11-06, Claude Code / Claude Opus 5.5)

**Drafted by Claude**
- `tasks/t02_on_call/`: task.md, setup.sql (shifts, doctors), spec.yaml
  (3 solo checks, 3 scenarios incl. a cross-shift liveness scenario),
  reference (`FOR UPDATE` on the shift's on-call rows), four wrong variants
  (w1 plain check-then-update, w2 REPEATABLE READ conditional UPDATE,
  w3 SERIALIZABLE without retry, w4 lock own row only), NOTES.md.
- `validate.py`: a `--task` run now writes `results/validation_partial.md`
  (gitignored) so it no longer overwrites the full `validation.md`.

**Verified by Claude**
- `make validate`: t01 and t02 all green; every counterexample reproduces.
- Reference trace inspected: R2 blocks on the `FOR UPDATE`, resumes with only
  its own row after R1 commits, and refuses. Exactly one doctor leaves in all
  24 schedules of the safety scenario.
- Observed a real Postgres SSI behaviour: SERIALIZABLE raises 40001 even
  for doctors in different shifts (relation-level predicate lock from a
  sequential scan on a tiny table).

**Human to review**
- `tasks/t02_on_call/task.md` wording (no hazard named; "only this doctor's
  row may change" is stated but only checked via solo `expect_sql` and the
  per-scenario "still on call" invariants).
- Whether the cross-shift scenario is fair: a real engineer using
  SERIALIZABLE must retry; the task states valid concurrent requests must
  succeed.
