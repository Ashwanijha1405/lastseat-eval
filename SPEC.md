# LastSeat — Build Spec

> Can frontier models write backend transaction code that stays correct when two users hit it at the same time?

This file is the single source of truth for building the eval. Read all of it before writing code.

Deadline: submissions close **Mon 9 Nov 2026, 05:15 GMT (10:45 AM IST)**. Target: submit **Sun 8 Nov night**.

---

## 1. What we are building (one paragraph)

Each task describes a realistic backend operation (buy stock, book a room, transfer money…) and a business invariant. The model under test writes a **Python function** that talks to PostgreSQL through a small `db` object we provide. Our harness then runs **two (sometimes three) concurrent requests** against a **real PostgreSQL 16** and uses a **deterministic scheduler** to explore **every interleaving** of their SQL statements. After each interleaving it checks the invariant. If any interleaving breaks the invariant, the model's code is unsafe — and we save that exact interleaving as a human-readable counterexample.

No LLM judge anywhere. Ground truth = real Postgres behaviour.

---

## 2. Non-negotiable principles (these map to the judging rubric)

1. **Deterministic grading.** Same code + same task ⇒ same verdict, every time, on any machine.
2. **Every task has a reference solution that passes** and **at least two deliberately wrong solutions that fail.** `validate` must prove this before any model is run.
3. **Everything the grader checks is stated in the task prompt.** No hidden requirements.
4. **Grade outcomes, not approach.** Models may use any isolation level, locks, constraints, migrations, retries — whatever a real engineer could do — unless the task states a real-world reason not to.
5. **Reproducible from a clean machine** with Docker and one documented command.
6. **Honest records.** Save raw model outputs, extracted code, verdicts, counterexample traces, model IDs, settings, dates, costs.
7. **AI-use log.** Append to `docs/AI_USE.md` what each Claude Code session drafted and what the human reviewed.

---

## 3. Repository layout

```
lastseat-eval/
├── README.md                 # written last (see §11)
├── SPEC.md                   # this file
├── CLAUDE.md                 # short working rules for Claude Code
├── docker-compose.yml        # db (postgres:16.x pinned) + eval (python) services
├── Dockerfile                # eval image: python 3.12-slim + requirements
├── requirements.txt          # pinned versions
├── .env.example              # OPENROUTER_API_KEY=, LASTSEAT_MAX_COST_USD=
├── Makefile                  # make up / validate / pilot / run / report / zip
├── lastseat/
│   ├── __init__.py
│   ├── db_api.py             # the `db` object given to model code
│   ├── scheduler.py          # interleaving explorer (core)
│   ├── sandbox.py            # load + restrict model code
│   ├── task.py               # task loader (spec.yaml)
│   ├── grade.py              # grade one solution file against one task
│   ├── validate.py           # run all references + wrong variants
│   ├── runner.py             # call models via OpenRouter, save outputs, grade
│   ├── report.py             # summary tables, pass^k, cost
│   └── prompts/contract.md   # API contract prepended to every task prompt
├── tasks/
│   └── t01_flash_sale/
│       ├── task.md           # exactly what the model sees (after contract.md)
│       ├── setup.sql         # schema (no seed rows)
│       ├── spec.yaml         # scenarios, invariants, checks (see §6)
│       ├── reference.py      # passes
│       ├── wrong/            # each file must FAIL, with a comment saying why
│       │   ├── w1_read_then_write.py
│       │   └── w2_....py
│       └── NOTES.md          # why this task is hard, expected failure modes
├── tests/                    # pytest: scheduler finds known races, passes known-safe code, is deterministic
├── results/<run_id>/...      # see §9
└── docs/AI_USE.md
```

---

## 4. The `db` API (what model code can use)

Model code receives a `db` object. Each concurrent request gets its own connection.

```python
db.begin(isolation: str = "read committed")   # "read committed" | "repeatable read" | "serializable"
db.execute(sql: str, params: dict | tuple | None = None) -> list[tuple]   # returns all rows (empty list if none)
db.commit()
db.rollback()
```

- Placeholders use psycopg style: `%(name)s` or `%s`.
- Outside `begin()`…`commit()`, each `execute` auto-commits (connection runs in autocommit mode; `begin` issues an explicit `BEGIN ISOLATION LEVEL …`).
- Database errors are raised as normal `psycopg.errors.*` exceptions (e.g. `SerializationFailure` = 40001, `DeadlockDetected` = 40P01, `UniqueViolation`, `ExclusionViolation`). Model code may catch them and retry.
- If a function returns while a transaction is still open, the harness rolls it back and records a warning.
- Optional: model may define `migrate(db)` — runs **once, alone**, after `setup.sql` and after the scenario's seed rows are inserted, before any request runs (changed 2026-11-07 from "before seeding": a real migration runs on a database that already holds data, so a constraint must accept the existing rows and a counter or summary table must be backfilled from them). Allowed: indexes, constraints, extensions (`btree_gist` is available), triggers, functions.
- A task may fix the schema with `allow_migrate: false` in spec.yaml (added 2026-11-07; first used by t08). Its task.md then says "Do not define migrate()" (validate checks this), and a module that defines `migrate` is rejected at load time with reason `forbidden_migrate`, before anything runs. Why: some real changes must ship without a schema review, and a schema change (a running-total column with a CHECK, say) would sidestep the locking discipline the task is testing. A wrong variant can expect this with `EXPECT: load_error forbidden_migrate`.

**Allowed imports in model code:** `psycopg.errors`, `datetime`, `decimal`, `typing`. Anything else ⇒ the solution is rejected with reason `forbidden_import`. No `time.sleep`, no threads, no network.

---

## 5. The scheduler (core engine) — `lastseat/scheduler.py`

### 5.1 Scheduling points
Every call to `db.begin`, `db.execute`, `db.commit`, `db.rollback` is a **step**. Before performing a step, the request's thread **pauses** and waits for the scheduler to let it go.

### 5.2 Thread states
`READY` (paused at a step, waiting for permission) · `RUNNING` (statement sent to Postgres) · `BLOCKED` (statement is waiting on a Postgres lock) · `DONE` (function returned or raised).

### 5.3 Detecting BLOCKED deterministically (no sleeps-as-logic)
Use a separate **monitor connection**. For a `RUNNING` thread, poll `SELECT cardinality(pg_blocking_pids(<backend_pid>)) > 0`. If true ⇒ `BLOCKED`. Each thread knows its own backend pid (`SELECT pg_backend_pid()` at connect).

### 5.4 Main loop (one schedule)
1. Reset the database (see §5.6). Open one connection per request.
2. Start all request threads. Each runs until its first step and becomes `READY`.
3. Loop:
   - Wait for **quiescence**: every thread is `READY`, `BLOCKED`, or `DONE` (a blocked thread can become unblocked when another commits — keep polling until stable). Global timeout per schedule (e.g. 15 s) ⇒ verdict `HARNESS_TIMEOUT` (treat as infrastructure error, not model failure; must never happen on references).
   - If all `DONE` ⇒ stop.
   - Collect `READY` threads. If none are `READY` but some are `BLOCKED` ⇒ wait (Postgres will resolve deadlocks; set `deadlock_timeout=50ms` in the db container so this is fast).
   - Pick the next `READY` thread according to the **choice sequence** (§5.5). Let it perform exactly one step.
4. After all done: run every invariant query from `spec.yaml` on a fresh connection. Record pass/fail per invariant, each request's return value or exception, and the full step **trace**.

Per-request step limit (e.g. 60) ⇒ verdict `STEP_LIMIT` (counts as liveness failure — e.g. infinite retry loop).

### 5.5 Exploring all interleavings (stateless DFS)
- A schedule is defined by its sequence of choices at each choice point (which `READY` thread goes next).
- Run schedule with a prefix; at each choice point beyond the prefix, take the lowest-index `READY` thread and record the alternatives.
- Backtrack: take the deepest choice point with an unexplored alternative, form the new prefix, re-run from a fresh database.
- Cap at `max_schedules` (default 2000). Report `exhaustive: true/false` and the number explored. If not exhaustive, also run N seeded-random schedules and record the seed.
- **Determinism check:** every failing schedule is re-run once from its choice sequence; record `reproduced: true/false`. Validation fails if any reference or wrong variant is non-reproducible.

### 5.6 Fast database reset
- Per task build a **template database**: apply `setup.sql`, then seed rows for the scenario, then the solution's `migrate(db)` if present. Then `CREATE DATABASE run_<n> TEMPLATE tmpl_<...>` for each schedule and drop it afterwards.
- If template creation is too slow in practice, fall back to: drop + recreate schema, re-apply setup, migrate, seed. Measure and document which is used.

### 5.7 Trace format (this becomes our "transcripts" for judges)
Each failing schedule saves a readable trace, e.g.

```
step 1  R1  BEGIN ISOLATION LEVEL REPEATABLE READ
step 2  R2  BEGIN ISOLATION LEVEL REPEATABLE READ
step 3  R1  SELECT count(*) FROM doctors WHERE shift_id=1 AND on_call   -> [(2,)]
step 4  R2  SELECT count(*) FROM doctors WHERE shift_id=1 AND on_call   -> [(2,)]
step 5  R1  UPDATE doctors SET on_call=false WHERE id=1                 -> ok
step 6  R2  UPDATE doctors SET on_call=false WHERE id=2                 -> ok
step 7  R1  COMMIT
step 8  R2  COMMIT
INVARIANT VIOLATED: every shift has >= 1 doctor on call  (shift 1 has 0)
```

---

## 6. Task format — `spec.yaml`

```yaml
id: t01_flash_sale
title: Flash-sale stock decrement
entrypoint: purchase            # function name the model must define
signature: "purchase(db, product_id: int, qty: int) -> bool"
seed_state_sql: |               # optional default seed; scenarios may override
  INSERT INTO products(id, stock) VALUES (1, 5);
invariants:                     # each query must return exactly one boolean: true = holds
  - name: stock never negative
    sql: SELECT bool_and(stock >= 0) FROM products
  - name: stock is conserved
    sql: >
      SELECT p.stock + COALESCE((SELECT sum(qty) FROM orders WHERE product_id = p.id), 0) = 5
      FROM products p WHERE p.id = 1
solo_checks:                    # run alone, sequentially, on a fresh db
  - name: enough stock succeeds
    seed_sql: INSERT INTO products VALUES (1, 5);
    call: {product_id: 1, qty: 3}
    expect_return: true
    expect_sql: SELECT stock = 2 FROM products WHERE id = 1
  - name: not enough stock is refused cleanly
    seed_sql: INSERT INTO products VALUES (1, 2);
    call: {product_id: 1, qty: 3}
    expect_return: false        # raising an exception here is a FAIL
    expect_sql: SELECT stock = 2 FROM products WHERE id = 1
concurrent_scenarios:
  - name: two buyers, only one can win
    seed_sql: INSERT INTO products VALUES (1, 5);
    requests:
      - {product_id: 1, qty: 3}
      - {product_id: 1, qty: 3}
    must_all_succeed: false     # safety only
  - name: two buyers, both fit
    seed_sql: INSERT INTO products VALUES (1, 6);
    requests:
      - {product_id: 1, qty: 3}
      - {product_id: 1, qty: 3}
    must_all_succeed: true      # liveness: both must return true in EVERY schedule (no 500s)
```

**Several functions per task** (added 2026-11-06). Instead of `entrypoint`, a task
may list `entrypoints: [approve_expense, edit_expense, change_budget]`; the model
must define all of them. Every `call` and every request then names its function:

```yaml
    requests:
      - {fn: approve_expense, args: {expense_id: 1}}
      - {fn: edit_expense, args: {expense_id: 2, new_amount: 400}}
```

The `{fn, args}` form also works in single-entrypoint tasks; the bare argument
mapping is only allowed when there is exactly one entrypoint. `success_means`
applies to every function of the task.

### 6.1 Scoring per task (per trial)
- **Safety (0.5):** all invariants hold in every explored schedule of every concurrent scenario,
  **and** at least one solo check that expects the operation to succeed passed
  (`expect_return: true`; with `success_means: returns`, any solo check).
  Otherwise safety is 0 and `verdict.json` records `"safety_reason": "vacuous_safety"`.
  *Why (added 2026-11-06 after the free pilot):* code that never performs the
  operation (Nemotron's t07 raised a syntax error on every call) cannot break an
  invariant, and was scored 0.5 for doing nothing. Per-scenario `safe` flags
  still report what the scheduler observed; only the score changes.
- **Solo correctness (0.25):** all solo checks pass.
- **Liveness (0.25):** in scenarios with `must_all_succeed: true`, every request returns `True` in every schedule (no exception escapes, no `STEP_LIMIT`).
- **Task PASS** = all three fully satisfied. Partial score reported separately.
- Code that fails to load (syntax error, missing function, forbidden import) = score 0 with reason recorded.

### 6.2 Why `must_all_succeed` matters
Without it, "make everything SERIALIZABLE and never retry" would trivially be safe while real users get errors. Real services must not fail valid requests just because another user clicked at the same time. This is stated explicitly in every task prompt.

---

## 7. The tasks (6 core + 1 stretch)

Each task folder gets `task.md`, `setup.sql`, `spec.yaml`, `reference.py`, ≥2 `wrong/*.py`, `NOTES.md`. The **harness is the source of truth**: if a reference fails or a wrong variant passes, investigate and fix our understanding — never edit the grader to force a result.

The task prompts must describe a realistic product situation in plain language, state the invariant, the function signature, the return-value contract, and that concurrent requests happen and valid concurrent requests must succeed. **Do not name the hazard** (never write "write skew", "phantom", "race condition", "deadlock") in the model-facing prompt.

| ID | Scenario | Hazard (internal only) | Role | Expected wrong patterns |
|---|---|---|---|---|
| t01 | Flash-sale stock decrement with `orders` table | Lost update | **Control** — frontier models should pass | read stock in app, write computed value |
| t02 | Hospital on-call rota: doctor goes off call; each shift keeps ≥1 on call | Write skew (textbook DDIA case) | **Textbook** | conditional UPDATE under REPEATABLE READ; check-then-update without locks |
| t03 | Department expense approvals: approving an expense must keep total approved ≤ department budget | Write skew where "lock the rows you read" does **not** work (the approved set changes, the newly approved row was never in it) | **Non-textbook twin of t02** | `FOR UPDATE` on approved rows only; REPEATABLE READ check-then-update |
| t04 | Meeting-room booking, half-open intervals, no overlaps per room | Phantom (no existing row to lock) | Core | `INSERT … WHERE NOT EXISTS`; `FOR UPDATE` on (empty) overlap query |
| t05 | Wallet transfer between two users; concurrent A→B and B→A must both succeed | Deadlock + retry / lock ordering | Core | update in argument order without retry; read-then-write balances |
| t06 | Payment creation with client idempotency key; two duplicate requests arriving together must create exactly one payment and **both** return the same payment id | Check-then-insert race; `INSERT … ON CONFLICT DO NOTHING` returning no row; snapshot visibility of the other request's row | Core / hardest | SELECT-then-INSERT; ON CONFLICT without re-reading; re-read inside a REPEATABLE READ snapshot |
| t07 (stretch) | Maintenance drain of a storage node: every shard must keep ≥1 active replica; draining affects several shards at once | Multi-group write skew + lock-order deadlocks | Stretch, only if time | per-shard checks without consistent lock order |

Reference solution ideas (verify each with the harness — do not trust these notes blindly):
- t01: single conditional `UPDATE … SET stock = stock - %(qty)s WHERE id = … AND stock >= %(qty)s RETURNING …`, insert order only if a row came back.
- t02: READ COMMITTED + `SELECT … FROM doctors WHERE shift_id = … AND on_call FOR UPDATE`, then conditional update; or SERIALIZABLE + bounded retry on 40001.
- t03: lock the **department row** (`SELECT … FROM departments WHERE id = … FOR UPDATE`) before summing; or SERIALIZABLE + retry.
- t04: `migrate()` adds `EXCLUDE USING gist (room_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)` and the insert catches `ExclusionViolation` → return False; or lock the `rooms` row first.
- t05: lock both account rows in a fixed order (by id), or retry on 40P01/40001 with a bounded loop.
- t06: unique constraint on the key via `migrate()`, `INSERT … ON CONFLICT DO NOTHING RETURNING id`; if no row, re-read the existing payment **in a statement that can see the committed row** (READ COMMITTED). Verify behaviour under other isolation levels with the harness and document it in NOTES.md.

Each task also has:
- **≥2 solo checks** (success path + clean refusal path).
- **≥2 concurrent scenarios**: one "only one may win" (safety) and one "both are valid" (`must_all_succeed: true`).

---

## 8. Model runner — `lastseat/runner.py`

- Provider: **OpenRouter** (OpenAI-compatible API, `base_url=https://openrouter.ai/api/v1`). Key from `OPENROUTER_API_KEY` env var only.
- Models are listed in `config/models.yaml`. Before the first real run, fetch `https://openrouter.ai/api/v1/models`, show the human the exact IDs and per-token prices for the candidates, and let the human confirm. **Do not guess model IDs.** Target set: 3 frontier models from different labs + 1 cheaper/open model.
- Prompt = `prompts/contract.md` + `tasks/<id>/task.md`. Same prompt for every model. No system-prompt tricks.
- Settings: provider default temperature unless the model allows setting it; record exactly what was sent (temperature, reasoning effort, max tokens) in the results. Use the same settings for all models where possible.
- Extract the **last** ```python fenced block. If none ⇒ `no_code` failure, saved.
- **Trials:** configurable; default 5 per model per task. Each trial is an independent request.
- **Cost guard:** read `usage` from each response, keep a running total, stop the run if `LASTSEAT_MAX_COST_USD` would be exceeded. Print an estimated cost before starting (based on pilot token counts).
- Retries only for transport errors (HTTP 429/5xx), with backoff; never re-sample because the answer looked bad.
- `--dry-run` mode using a mock model that returns the reference solution (to test the pipeline at zero cost).

---

## 9. Results layout

```
results/<run_id>/
├── run_meta.json            # date, git commit, models + exact IDs, settings, trials, postgres version, scheduler caps
├── <model_slug>/<task_id>/trial_<n>/
│   ├── prompt.txt
│   ├── raw_response.txt
│   ├── solution.py
│   ├── verdict.json         # scores, per-scenario results, schedules explored, exhaustive flag, cost, tokens
│   └── counterexample_<k>.txt   # readable trace for each distinct failing schedule (cap at 3)
└── summary.md               # table: model | trials/task | pass rate | pass^k | mean partial score | cost
```

`report.py` also produces a per-task matrix (model × task, with ✅ / ⚠️ inconsistent / ❌) and a short list of failure categories per task for the human to analyse.

---

## 10. Commands (Makefile targets; everything runs inside Docker)

```
make up          # start postgres (pinned 16.x, deadlock_timeout=50ms)
make test        # pytest: scheduler unit tests
make validate    # all references PASS, all wrong variants FAIL, all failures reproducible -> writes results/validation.md
make pilot       # 1 trial, chosen models, all tasks
make run         # full run (trials=5)
make report RUN=<run_id>
make zip         # builds submission zip: excludes .env, caches, large files; checks size < 50 MB; greps for API keys
```

Target: a judge runs `cp .env.example .env`, adds a key, `make up && make validate && make run` — nothing else.

---

## 11. README.md (written last, by the human with help) must contain

1. Short description (domain, gap, key finding) + video link
2. Domain & expertise (honest: student building a production backend; what experience informed the tasks)
3. What it tests & why it matters (double-booking, overselling, lost money)
4. Setup & run (one command where possible), API key via env, runtime and cost
5. Models tested: exact IDs, run date, settings, trials, scores (pass rate + pass^k)
6. Grader validation table from `make validate`
7. Per-task failure analysis with links to counterexample traces (written by the human from the transcripts)
8. Main failure mode + hot take
9. Prior work & sources (Jepsen/Elle, Berenson et al. "A Critique of ANSI SQL Isolation Levels", PostgreSQL docs on transaction isolation, Kleppmann DDIA write-skew example, related LLM benchmarks such as CONCUR) and what existed before vs built during the hackathon
10. AI use: what Claude/Claude Code drafted, what the human reviewed and changed

---

## 12. Build order (milestones — stop after each for human review + git commit)

- **M0** skeleton, docker-compose, Dockerfile, Makefile, CLAUDE.md, docs/AI_USE.md, `.gitignore` (must ignore `.env`).
- **M1** `db_api.py` + `scheduler.py` + `tests/`: a toy lost-update program must be caught; a toy safe program must pass; same schedule twice ⇒ same trace.
- **M2** task loader + `grade.py` + **t01 complete** (task, spec, reference, wrong variants). `make validate` green for t01.
- **M3** t02–t06 drafted one at a time; after each, `make validate` for that task and show the human the counterexample of each wrong variant.
- **M4** runner with `--dry-run`, cost guard, model-ID confirmation step.
- **M5** pilot run (1 trial). Human reads outputs. Adjust tasks only for clarity bugs (never to make models fail on purpose); log every change in NOTES.md.
- **M6** full run + report.
- **M7** `make zip`, clean-clone reproduction test (fresh directory, follow README only).

If time runs short: drop t07 first, then reduce trials from 5 to 3. Never drop validation.
