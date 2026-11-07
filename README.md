# LastSeat

**Can frontier models write backend transaction code that stays correct when two users hit it at the same time?**

LastSeat gives a model a realistic backend operation (sell the last item in stock, book a room, move money between wallets, approve an expense against a budget) and the business rule it must keep. The model writes Python functions that talk to PostgreSQL. The harness then runs two or three of those requests **concurrently against real PostgreSQL 16** under a **deterministic scheduler** that tries every interleaving of their SQL statements, and checks the rule after each one. One bad interleaving fails the task, and the exact interleaving is saved as a readable counterexample. There is no LLM judge: the ground truth is what Postgres actually does.

> **TODO-HUMAN:** one-sentence key finding (see sections 5 and 8).

Video: **TODO-HUMAN: link**

---

## 1. Short description

- **Domain:** backend engineering, specifically transactional database code under concurrency (isolation levels, row and advisory locks, constraints, retries).
- **Gap:** code benchmarks run model code once, sequentially. Concurrency bugs (lost updates, write skew, phantoms, deadlocks, check-then-insert races) only show up when requests interleave, and a single test run almost never hits the bad interleaving. LastSeat explores the interleavings systematically and deterministically.
- **Key finding:** TODO-HUMAN (above).

## 2. Domain & expertise

> **TODO-HUMAN:** who built this and why (student building production backends; which experiences informed the tasks).

## 3. What it tests & why it matters

Overselling, double-booking and lost money are what happens when this code is wrong, and the bugs are invisible in ordinary testing: each request is correct on its own. Each task's prompt states the product situation, the invariant, the function signatures and return contract, that requests arrive concurrently, and that valid concurrent requests must succeed. **Prompts never name the hazard** (no "write skew", "phantom", "race", "deadlock").

| task | situation | hazard (internal, not in the prompt) |
|---|---|---|
| t01_flash_sale | flash-sale checkout decrements stock | lost update (control task) |
| t02_on_call | doctor goes off call; each shift keeps ≥1 on call | write skew (textbook DDIA case) |
| t03_expense_budget | approve expense; total approved ≤ department budget | write skew where locking the rows you read is not enough |
| t04_room_booking | book a room; bookings never overlap | phantom (no existing row to lock) |
| t05_wallet_transfer | A→B and B→A transfers arrive together | deadlock: lock ordering or retry |
| t06_idempotent_payment | duplicate "Pay" requests with one idempotency key | check-then-insert race; `ON CONFLICT` visibility |
| t07_node_drain | drain storage nodes; every shard keeps an active replica | multi-group write skew and lock-order deadlocks |
| t08_expense_endpoints | approve, edit amount, change budget, all concurrently | write skew across several endpoints |
| t09_room_rules | book, reschedule (across days), cancel; no overlap and ≤3 bookings per room per UTC day | phantoms and per-day counts across two days |
| t10_room_rules_scaled | t09 plus: requests for different rooms, or different days of one room, must never wait for each other | as t09, but coarse locking also fails (`must_not_block`) |

**Scoring (per trial).** Safety 0.5: no explored interleaving breaks an invariant (and only counts once the code has succeeded at least once alone, so code that never does anything gets no safety credit). Solo correctness 0.25: every single-request check passes. Liveness 0.25: in scenarios where all requests are valid, all of them succeed in every interleaving; in `must_not_block` scenarios (t10) no request ever waits for another's lock. A trial **passes** only with all three. Models may use any technique a real engineer could: isolation levels, row or advisory locks, constraints added in a `migrate()` function, bounded retries. Details: [SPEC.md](SPEC.md) §4–§6.

**How the scheduler works.** Each request runs on its own Postgres connection and pauses before every SQL statement. The scheduler resumes one request at a time; a request is BLOCKED when `pg_blocking_pids()` shows it waiting for another's lock (never timing-based). It explores interleavings with a stateless depth-first search, re-running each schedule from a fresh database copy, and re-runs every failing schedule to confirm the same trace. Caps per scenario: 2000 DFS schedules, then 200 seeded-random ones; every schedule a model was graded on is recorded as exhaustive or not (section 4).

## 4. Setup & run

Requirements: Docker (with Compose) and `make`, or PowerShell on Windows (`.\run.ps1` has the same commands). Everything runs in containers: `postgres:16.15-bookworm` and `python:3.12.16-slim-bookworm`, all Python packages pinned ([requirements.txt](requirements.txt)).

```sh
cp .env.example .env          # API keys only needed for model runs (below)
make up && make validate      # Windows: .\run.ps1 validate
```

`make validate` grades every reference and wrong variant and writes [results/validation.md](results/validation.md); `make test` runs the unit tests.

Model runs:

| route | command | needs |
|---|---|---|
| OpenRouter, free models | `make run CONFIG=free TRIALS=3 YES=1` (`.\run.ps1 run -Config free -Trials 3 -Yes`) | `OPENROUTER_API_KEY`; `LASTSEAT_MAX_COST_USD` empty or `0` (a free run refuses anything else and sends `max_price: 0`) |
| OpenRouter, paid models | `make run CONFIG=paid YES=1` | `OPENROUTER_API_KEY`, `LASTSEAT_MAX_COST_USD` > 0 (hard stop); model IDs in [config/models.yaml](config/models.yaml) must be confirmed first |
| Claude Code headless | `.\run.ps1 official-cli -Model claude-opus-5-5 -New -Yes` | Claude Code logged in with a claude.ai account; no API key is read (all `ANTHROPIC_*`/`CLAUDE*` env vars are removed for the call) |
| Gemini via Antigravity CLI | `.\run.ps1 official-cli -Cli antigravity -Model gemini-3.8-flash-high -New -Yes` | `agy` signed in with a Google account |

The official-CLI route is wired in `run.ps1` only. On Linux/macOS run its three steps by hand: `python -m lastseat.official_cli prepare ...` (in Docker), `python lastseat/cli_host.py results/<run>` (on the host, standard library only), `python -m lastseat.official_cli grade results/<run>` (in Docker). A run never starts implicitly: an unfinished run is resumed only by `RUN=<id>` / `-Run <id>`, a new one only with `NEW=1` / `-New`. The README tables below are regenerated from `results/` with `python -m lastseat.report --write`.

**Runtime and cost** of the final runs (from `results/`):

<!-- BEGIN report:runtime -->
| model | new calls in the final run (reused pilot trials excluded) | model time per answer (median s) | grading time (total s) | schedules explored | scenarios not exhaustive | spent (USD) |
|---|---|---|---|---|---|---|
| `claude-opus-5-5` | 15 | 18 | 1258 | 40436 | 5 of 144 | 0.00 |
| `claude-sonnet-5-5` | 30 | 12 | 1458 | 49127 | 7 of 144 | 0.00 |
| `claude-haiku-5-5` | 24 | 0 | 0 | 0 | 0 of 0 | 0.00 |
| `gemini-3.8-flash-high` | 19 | 335 | 576 | 17570 | 0 of 132 | 0.00 |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 27 | 119 | 994 | 31402 | 8 of 82 | 0.00 |

Grader validation (`make validate`, 53 solutions): 21 min of grading time on the machine that produced these results (sum of per-solution times; Docker Desktop on Windows 11).
<!-- END report:runtime -->

## 5. Models tested

<!-- BEGIN report:models -->
| model (exact ID) | route | settings | trials | run dates (UTC) | cells graded | run |
|---|---|---|---|---|---|---|
| `claude-opus-5-5` | Claude Code `claude -p` 2.1.319, claude.ai Pro login | effort `high`, no tools (`--tools ''`), CLI system prompt included | 3 per task | 2026-11-07 | 30/30 (15 reused from pilots) | [`final-claude-opus-5-5-cli`](results/final-claude-opus-5-5-cli/summary.md) |
| `claude-sonnet-5-5` | Claude Code `claude -p` 2.1.319, claude.ai Pro login | effort `high`, no tools (`--tools ''`), CLI system prompt included | 3 per task | 2026-11-07 | 30/30 | [`final-claude-sonnet-5-5-cli`](results/final-claude-sonnet-5-5-cli/summary.md) |
| `claude-haiku-5-5` | Claude Code `claude -p` 2.1.319, claude.ai Pro login | effort `high`, no tools (`--tools ''`), CLI system prompt included | 3 per task | - | 0/30 | [`final-claude-haiku-5-5-cli`](results/final-claude-haiku-5-5-cli/summary.md) |
| `gemini-3.8-flash-high` | Antigravity CLI `agy --print` 1.5.3, Google sign-in | `-high` variant chosen by model id, every tool action denied, CLI system prompt included | 3 per task | 2026-11-07 | 30/30 (12 reused from pilots) | [`final-gemini-3.8-flash-high-cli`](results/final-gemini-3.8-flash-high-cli/summary.md) |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | OpenRouter free tier (served by Nvidia) | reasoning effort `high`, max_tokens 32000, max_price 0 | 3 per task | 2026-11-07 | 27/30 | [`final-free-nemotron-3-ultra`](results/final-free-nemotron-3-ultra/summary.md) |
<!-- END report:models -->

All final runs use the same frozen tasks t01–t10, the same prompt (contract + `task.md`), and 3 trials per task. Where a final run reuses pilot trials, the model, CLI, effort and prompt were identical, and the reused answers were graded again by the current grader (listed per run in its `summary.md`).

**Results** (trials passed out of 3 per task; ✅ = pass^3, all three trials passed):

<!-- BEGIN report:results -->
| task | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` | `gemini-3.8-flash-high` | `nvidia/nemotron-3-ultra-550b-a55b:free` |
|---|---|---|---|---|---|
| t01_flash_sale | 3/3 ✅ | 3/3 ✅ | running | 3/3 ✅ | 3/3 ✅ |
| t02_on_call | 3/3 ✅ | 3/3 ✅ | running | 3/3 ✅ | 3/3 ✅ |
| t03_expense_budget | 3/3 ✅ | 3/3 ✅ | running | 3/3 ✅ | 3/3 ✅ |
| t04_room_booking | 3/3 ✅ | 3/3 ✅ | running | 3/3 ✅ | 0/3 ❌ |
| t05_wallet_transfer | 3/3 ✅ | 3/3 ✅ | running | 3/3 ✅ | 3/3 ✅ |
| t06_idempotent_payment | 3/3 ✅ | 3/3 ✅ | running | 3/3 ✅ | 2/3 ❌ |
| t07_node_drain | 3/3 ✅ | 3/3 ✅ | running | 3/3 ✅ | 1/3 ❌ |
| t08_expense_endpoints | 3/3 ✅ | 3/3 ✅ | running | 3/3 ✅ | 2/2 (running) |
| t09_room_rules | 3/3 ✅ | 3/3 ✅ | running | 3/3 ✅ | 0/2 (running) |
| t10_room_rules_scaled | 3/3 ✅ | 3/3 ✅ | running | 2/3 ❌ | 1/2 (running) |
| **trials passed** | 30/30 | 30/30 | 0/0 of 30 | 29/30 | 18/27 of 30 |
| **mean score** | 1.000 | 1.000 | - | 0.967 | 0.694 |
| **tasks with pass^3** | 10/10 | 10/10 | 0/10 | 9/10 | 4/10 |
| **latent_api_error warnings** | 0 | 0 | 0 | 4 | 0 |
<!-- END report:results -->

Per-trial scores, failure details and API records: each run's `summary.md` (linked above). `latent_api_error` is a static warning that never changes a score: the solution references a `psycopg.errors` name the pinned psycopg does not define, which crashes only if that line ever runs.

### Limitations

- **CLI-routed models include the CLI's own system prompt.** Claude models ran through Claude Code headless (`claude -p`, tools disabled) and Gemini through Antigravity CLI (`agy --print`, every tool action denied). Both add their own agent system prompt before ours, so these cells are not directly comparable with API cells.
- **Gemini is Gemini 3.8 Flash (`-high` variant) via Antigravity CLI, not Argon.** The free Google sign-in route offers no Argon model.
- **Antigravity's built-in web search cannot be denied.** In one Gemini call (t04 trial 2) the model ran `search_web`; the harness stopped, never graded that answer, and asked again with unchanged settings (recorded in that run's `run_meta.json`). No graded answer ran any tool.
- **Free models via OpenRouter**, with the free tier's daily request cap and whatever upstream provider OpenRouter routes to (recorded per trial).
- **No parallelism scoring beyond `must_not_block`.** A solution that serializes more than needed passes every task except t10. Retry-heavy solutions also pass: on t10 a SERIALIZABLE + bounded-retry solution passes without ever waiting, though most of its schedules hit serialization failures and retry.
- **Statement-level interleavings.** The scheduler switches between requests only at SQL statement boundaries (plus the lock waits Postgres reports). Scenarios have two or three requests and small seed data; where the 2000-schedule cap is reached, 200 seeded-random schedules are added and the scenario is marked not exhaustive (counted in section 4).
- **Small task count and few trials:** 10 tasks (t09/t10 share a schema and rules), 3 trials per task, so pass^3 is a coarse reliability measure.
- **One machine, one Postgres version** (16.15); behaviour of other databases or isolation implementations is not covered.

## 6. Grader validation

Every task ships a reference solution that must pass and several deliberately wrong variants, each declaring (`EXPECT:` in its docstring) exactly which components it must fail. Every failing schedule must reproduce on re-run.

<!-- BEGIN report:validation -->
| task | solution | expected | observed failures | schedules explored | exhaustive | result |
|---|---|---|---|---|---|---|
| t01_flash_sale | `reference.py` | PASS | none (PASS) | 48 | yes | ✅ |
| t01_flash_sale | `wrong/w1_read_then_write.py` | fail safety | safety | 184 | yes | ✅ |
| t01_flash_sale | `wrong/w2_repeatable_read_no_retry.py` | fail liveness | liveness | 48 | yes | ✅ |
| t01_flash_sale | `wrong/w3_check_then_decrement.py` | fail safety | safety | 184 | yes | ✅ |
| t01_flash_sale | `wrong/w4_nowait_refuses.py` | fail liveness | liveness | 160 | yes | ✅ |
| t02_on_call | `reference.py` | PASS | none (PASS) | 118 | yes | ✅ |
| t02_on_call | `wrong/w1_check_then_update.py` | fail safety | safety | 210 | yes | ✅ |
| t02_on_call | `wrong/w2_repeatable_read_conditional_update.py` | fail safety | safety | 60 | yes | ✅ |
| t02_on_call | `wrong/w3_serializable_no_retry.py` | fail liveness | liveness | 210 | yes | ✅ |
| t02_on_call | `wrong/w4_lock_own_row_only.py` | fail safety | safety | 756 | yes | ✅ |
| t03_expense_budget | `reference.py` | PASS | none (PASS) | 360 | yes | ✅ |
| t03_expense_budget | `wrong/w1_check_then_update.py` | fail safety | safety | 3696 | yes | ✅ |
| t03_expense_budget | `wrong/w2_lock_approved_rows_sum_in_python.py` | fail safety | safety | 2548 | yes | ✅ |
| t03_expense_budget | `wrong/w3_department_lock_repeatable_read.py` | fail safety | safety | 1074 | yes | ✅ |
| t03_expense_budget | `wrong/w4_lock_approved_rows_then_sum.py` | fail safety | safety | 2144 | yes | ✅ |
| t04_room_booking | `reference.py` | PASS | none (PASS) | 54 | yes | ✅ |
| t04_room_booking | `wrong/w1_check_then_insert.py` | fail safety | safety | 210 | yes | ✅ |
| t04_room_booking | `wrong/w2_insert_where_not_exists.py` | fail safety | safety | 18 | yes | ✅ |
| t04_room_booking | `wrong/w3_for_update_on_empty_result.py` | fail safety | safety | 210 | yes | ✅ |
| t04_room_booking | `wrong/w4_repeatable_read_check_then_insert.py` | fail safety | safety | 210 | yes | ✅ |
| t04_room_booking | `wrong/w5_closed_range_constraint.py` | fail liveness+solo | solo, liveness | 48 | yes | ✅ |
| t05_wallet_transfer | `reference.py` | PASS | none (PASS) | 108 | yes | ✅ |
| t05_wallet_transfer | `wrong/w1_argument_order_no_retry.py` | fail liveness | liveness | 78 | yes | ✅ |
| t05_wallet_transfer | `wrong/w2_read_then_write_balances.py` | fail liveness+safety | safety, liveness | 1120 | yes | ✅ |
| t05_wallet_transfer | `wrong/w3_check_then_relative_update.py` | fail liveness+safety | safety, liveness | 296 | yes | ✅ |
| t05_wallet_transfer | `wrong/w4_serializable_retry_40001_only.py` | fail liveness | liveness | 296 | yes | ✅ |
| t06_idempotent_payment | `reference.py` | PASS | none (PASS) | 14 | yes | ✅ |
| t06_idempotent_payment | `wrong/w1_select_then_insert.py` | fail liveness+safety | safety, liveness | 210 | yes | ✅ |
| t06_idempotent_payment | `wrong/w2_on_conflict_no_reread.py` | fail liveness+solo | solo, liveness | 14 | yes | ✅ |
| t06_idempotent_payment | `wrong/w3_reread_in_repeatable_read.py` | fail liveness | liveness | 48 | yes | ✅ |
| t06_idempotent_payment | `wrong/w4_unique_but_unhandled.py` | fail liveness | liveness | 170 | yes | ✅ |
| t07_node_drain | `reference.py` | PASS | none (PASS) | 324 | yes | ✅ |
| t07_node_drain | `wrong/w1_check_then_update.py` | fail safety | safety | 210 | yes | ✅ |
| t07_node_drain | `wrong/w2_deactivate_then_verify.py` | fail liveness | liveness | 130 | yes | ✅ |
| t07_node_drain | `wrong/w3_per_shard_locks_unsorted.py` | fail liveness | liveness | 568 | yes | ✅ |
| t07_node_drain | `wrong/w4_sorted_lock_repeatable_read.py` | fail safety | safety | 324 | yes | ✅ |
| t08_expense_endpoints | `reference.py` | PASS | none (PASS) | 468 | yes | ✅ |
| t08_expense_endpoints | `wrong/w1_unprotected_edit.py` | fail safety | safety | 1262 | yes | ✅ |
| t08_expense_endpoints | `wrong/w2_unprotected_change_budget.py` | fail safety | safety | 417 | yes | ✅ |
| t08_expense_endpoints | `wrong/w3_edit_locks_expense_row.py` | fail safety | safety | 1926 | yes | ✅ |
| t08_expense_endpoints | `wrong/w4_edit_pending_without_lock.py` | fail safety | safety | 637 | yes | ✅ |
| t08_expense_endpoints | `wrong/w5_running_total_column.py` | fail load_error:forbidden_migrate | load_error `forbidden_migrate` | - | - | ✅ |
| t09_room_rules | `reference.py` | PASS | none (PASS) | 1387 | yes | ✅ |
| t09_room_rules | `wrong/w1_exclusion_constraint_only.py` | fail safety | safety | 982 | yes | ✅ |
| t09_room_rules | `wrong/w2_single_statement_checks.py` | fail safety | safety | 295 | yes | ✅ |
| t09_room_rules | `wrong/w3_reschedule_locks_days_in_move_order.py` | fail liveness | liveness | 1299 | yes | ✅ |
| t09_room_rules | `wrong/w4_lock_day_rows_count_them.py` | fail liveness+safety | safety, liveness | 469 | yes | ✅ |
| t10_room_rules_scaled | `reference.py` | PASS | none (PASS) | 2374 | yes | ✅ |
| t10_room_rules_scaled | `wrong/w1_exclusion_constraint_only.py` | fail safety | safety | 1263 | yes | ✅ |
| t10_room_rules_scaled | `wrong/w2_single_statement_checks.py` | fail safety | safety | 380 | yes | ✅ |
| t10_room_rules_scaled | `wrong/w3_reschedule_locks_days_in_move_order.py` | fail liveness | liveness | 2616 | yes | ✅ |
| t10_room_rules_scaled | `wrong/w4_lock_day_rows_count_them.py` | fail liveness+safety | safety, liveness | 750 | yes | ✅ |
| t10_room_rules_scaled | `wrong/w5_whole_room_lock.py` | fail liveness (blocking only) | liveness (blocked_independent_requests) | 1086 | yes | ✅ |
| t10_room_rules_scaled | `alternatives/serializable_retry.py` | PASS (alternative; graded separately, not by validate) | none (PASS) | 1358 | yes | ✅ |

10 references and 43 wrong variants; 53/53 behave as expected. Full table with per-scenario counts and counterexample links: [results/validation.md](results/validation.md).
<!-- END report:validation -->

## 7. Failure analysis

> **TODO-HUMAN:** per-task analysis written from the counterexample traces and transcripts.

Every failed final-run trial, with its category and files:

<!-- BEGIN report:failures -->
- `gemini-3.8-flash-high` · t10_room_rules_scaled · trial_2: **load** (exec_error): `AttributeError: module 'psycopg.errors' has no attribute 'TransactionRollbackError'` — [verdict](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t10_room_rules_scaled/trial_2/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t04_room_booking · trial_1: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t04_room_booking/trial_1/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t04_room_booking · trial_2: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t04_room_booking/trial_2/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t04_room_booking · trial_3: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t04_room_booking/trial_3/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t06_idempotent_payment · trial_2: **load** (migrate_error): `SyntaxError: syntax error at or near "NOT"` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t06_idempotent_payment/trial_2/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t07_node_drain · trial_1: **load** (forbidden_import): `collections` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_1/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t07_node_drain · trial_3: **spec** (vacuous_safety) — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/verdict.json), [counterexample 1](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/counterexample_1.txt), [counterexample 2](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/counterexample_2.txt), [counterexample 3](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/counterexample_3.txt)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t09_room_rules · trial_1: **spec** — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t09_room_rules/trial_1/verdict.json), [counterexample 1](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t09_room_rules/trial_1/counterexample_1.txt)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t09_room_rules · trial_2: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone, unknown) does not exis…` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t09_room_rules/trial_2/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t10_room_rules_scaled · trial_1: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_1/verdict.json)

Warnings (not scored):

- `gemini-3.8-flash-high` · t01_flash_sale · trial_2: `latent_api_error` `psycopg.errors.TransactionRollbackError` (line 27) — [solution](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t01_flash_sale/trial_2/solution.py)
- `gemini-3.8-flash-high` · t01_flash_sale · trial_3: `latent_api_error` `psycopg.errors.TransactionRollbackError` (line 33) — [solution](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t01_flash_sale/trial_3/solution.py)
- `gemini-3.8-flash-high` · t08_expense_endpoints · trial_2: `latent_api_error` `psycopg.errors.TransactionRollbackError` (line 53, 113, 154) — [solution](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t08_expense_endpoints/trial_2/solution.py)
- `gemini-3.8-flash-high` · t10_room_rules_scaled · trial_2: `latent_api_error` `psycopg.errors.TransactionRollbackError` (line 8) — [solution](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t10_room_rules_scaled/trial_2/solution.py)
<!-- END report:failures -->

Categories: **load** = never graded (syntax, import, missing function, `migrate_error`, `forbidden_migrate`, no code); **concurrency** = an invariant broke in some schedule, or a valid request failed or waited (liveness); **spec** = wrong when run alone (a solo check failed) with no unsafe schedule; **harness** = the grader failed.

## 8. Main failure mode + hot take

> **TODO-HUMAN.**

## 9. Prior work & sources

- **Jepsen** (Kyle Kingsbury), black-box testing of distributed databases under faults: <https://jepsen.io>. **Elle**: K. Kingsbury, P. Alvaro, "Elle: Inferring Isolation Anomalies from Experimental Observations", PVLDB 14(3), 2020. Jepsen and Elle test the *database*; LastSeat holds the database fixed and tests the *application code* a model writes against it.
- H. Berenson, P. Bernstein, J. Gray, J. Melton, E. O'Neil, P. O'Neil, "A Critique of ANSI SQL Isolation Levels", SIGMOD 1995: the anomaly vocabulary (lost update, write skew, phantom) used to design the tasks.
- **PostgreSQL 16 documentation, Transaction Isolation**: <https://www.postgresql.org/docs/16/transaction-iso.html>. In particular READ COMMITTED's re-check: an `UPDATE`/`DELETE`/`SELECT … FOR UPDATE` that waits for a concurrent writer re-evaluates its `WHERE` clause against the newest row version once that writer commits. This is why t01's single conditional `UPDATE` is safe, and why a read followed by a separate write is not. Also the SERIALIZABLE (SSI) and explicit locking chapters.
- M. Kleppmann, *Designing Data-Intensive Applications*, O'Reilly 2017, ch. 7: the doctors-on-call write-skew example that t02 follows (t03 is its non-textbook twin, where locking the rows you read does not help).
- **CONCUR**, an LLM benchmark for concurrent code generation. **TODO-HUMAN: verify authors, year and link.**
- **REFUTE** (counterexample creation for incorrect solutions) and **TestCase-Eval** (fault-exposing test generation): the idea of judging code by a concrete failing input, here a failing interleaving. **TODO-HUMAN: verify authors, year and links.**

**What existed before vs built during the hackathon.** Existing: PostgreSQL, psycopg, Docker, and the ideas above. Built during the hackathon: everything in this repository: the scheduler and `db` API, the ten tasks with references and wrong variants, the grader and validator, the OpenRouter runner with its zero-spend guards, the official-CLI providers, and the reports.

## 10. AI use

Claude Code (Claude Opus 5.5) drafted most code, tests, task files and this README's structure. The human reviewed each milestone. The session-by-session log of what was drafted and what needed review is [docs/AI_USE.md](docs/AI_USE.md). Rules Claude worked under: [CLAUDE.md](CLAUDE.md).

> **TODO-HUMAN:** reflection: what you reviewed and changed, what you would not have caught, what you learned.
