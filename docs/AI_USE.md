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
