# LastSeat eval: working rules

**Goal.** An eval (micro1 Eval Hackathon) testing whether frontier LLMs write
concurrency-safe PostgreSQL transaction code. A deterministic interleaving
scheduler runs model-written functions concurrently against real Postgres 16
in Docker and checks business invariants after every interleaving.
`SPEC.md` is the single source of truth; read it fully before any work.

## Rules

1. **One milestone per turn**, in the order of SPEC.md §12. After it, stop and
   report: what was built, how to run/verify it, what the human should check.
   Wait for "go" before the next milestone.
2. **The human is a student learning this area.** Before writing each
   non-trivial component, explain the logic in plain language (what, why, how).
   For new concepts (MVCC, isolation levels, row locks, `pg_blocking_pids`,
   stateless DFS), explain line by line where it matters.
3. **Never edit the grader or scheduler to force a result.** If a reference
   fails or a wrong variant passes, stop and explain what Postgres actually did.
4. **No API keys** in code, logs, or commits. `.env` is gitignored and
   dockerignored; keys come from env vars only.
5. **After each milestone**, append to `docs/AI_USE.md`: what Claude drafted,
   what the human needs to review.
6. **Pin all versions** (Postgres image tag, Python packages incl. transitive).
7. **No paid model API calls** until M4, and only after the human confirms
   model IDs and budget.

## Running things

Everything runs in Docker: `make up`, `make test` (see `make help`).
The db container uses `deadlock_timeout=50ms`, `autovacuum=off`, and
durability-only speedups; `tests/test_infra.py` asserts all of these.
