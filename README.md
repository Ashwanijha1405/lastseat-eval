# LastSeat

**Can AI models write backend transaction code that stays correct when two users act at the same moment?**

LastSeat is an evaluation for the micro1 Eval Hackathon. Models write Python functions that talk to PostgreSQL; a deterministic scheduler runs concurrent requests against a real PostgreSQL 16 server, explores the interleavings of their SQL statements, and checks the business rule after each one. There is no LLM judge: the verdict is what Postgres actually did.

<!-- BEGIN report:overview -->
| model | route | trials passed | tasks passed in all 3 trials (pass^3) | mean score | concurrency failures |
|---|---|---|---|---|---|
| `claude-opus-5-5` | official CLI (Claude Code) | 30/30 | 10/10 | 1.000 | 0 |
| `claude-sonnet-5-5` | official CLI (Claude Code) | 30/30 | 10/10 | 1.000 | 0 |
| `claude-haiku-5-5` | official CLI (Claude Code) | 29/30 | 9/10 | 0.983 | 0 |
| `gemini-3.8-flash-high` | official CLI (Antigravity) | 29/30 | 9/10 | 0.967 | 0 |
| `cohere/north-mini-code:free` | OpenRouter API (free tier) | 14/30 | 2/10 | 0.575 | 4 |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | OpenRouter API (free tier) | 20/30 | 5/10 | 0.700 | 0 |
<!-- END report:overview -->

Final runs, 10 tasks × 3 trials per model, all at $0. The Claude and Gemini models ran through their vendors' official CLIs, which add their own system prompt, so they are not directly comparable with the two OpenRouter API rows. Details and per-task results are in section 6.

---

## 1. Short description

LastSeat tests whether AI models write backend database code (selling the last item in stock, booking rooms, approving spend against a budget) that stays correct when two users act at the same moment. Each of its 10 tasks asks for Python functions that use PostgreSQL. A deterministic scheduler runs two concurrent requests on a real PostgreSQL 16 server in the possible orderings of their SQL statements, checks the business rule after each, and saves any violation as a reproducible step-by-step trace; there is no LLM judge, and the grader catches all 43 deliberately wrong solutions, 40 of which fail only under concurrency. Across 3 trials per task, Claude Opus 5.5 and Claude Sonnet 5.5 passed 30/30, Claude Haiku 5.5 and Gemini 3.8 Flash (high) 29/30, and the free models Nemotron 3 Ultra and Cohere North Mini Code (via OpenRouter) 20/30 and 14/30. In these tasks and runs the frontier models produced no race conditions; most failures (19 of 28) were code that could not load or set up its database, or no code at all, and only Cohere's code broke under true concurrency.

## 2. Video walkthrough

<https://youtu.be/k-UmPvdfJHE>

## 3. Domain and expertise

I'm a third-year B.Tech CSE (AI/ML) student at MAIT, Delhi (class of 2028). I was recently selected for the backend team at Delta-V, an early-stage scientific-ML startup project, and I'm studying system design (HLD/LLD) and Postgres internals: isolation levels, locking and MVCC. This eval grew out of that work: double-booking and overselling are exactly the bugs I'm learning to prevent.

I do not have years of industry experience. The tasks come from the textbook cases of this domain (lost update, write skew, phantoms, deadlocks, idempotency) set in product situations a backend team ships. The Postgres behaviour each task relies on was checked by running it (section 7), not taken from memory.

## 4. What it tests and why it matters

Backend teams that ship booking, inventory, payments and approval flows rely on transaction code like this. When it is wrong under concurrency, the cost is concrete: a room booked twice, stock sold below zero, a budget overspent, a payment created twice for one click. These bugs are hard to catch with ordinary tests, because each request is correct on its own and a normal test runs requests one after another. The bad ordering of statements needs two requests to overlap at one specific point, which a single test run almost never hits.

LastSeat makes that overlap systematic. Each task's prompt states the product situation, the business rule, the function signatures and return contract, that requests arrive concurrently, and that valid concurrent requests must succeed. **The prompts never name the hazard** (no "race", "write skew", "phantom", "deadlock").

| task | situation | hazard (internal, not in the prompt) |
|---|---|---|
| t01_flash_sale | flash-sale checkout decrements stock | lost update (control task) |
| t02_on_call | doctor goes off call; each shift keeps at least 1 on call | write skew (textbook case) |
| t03_expense_budget | approve an expense; total approved stays within the department budget | write skew where locking the rows you read is not enough |
| t04_room_booking | book a room; bookings never overlap | phantom (no existing row to lock) |
| t05_wallet_transfer | A→B and B→A transfers arrive together | deadlock: lock ordering or retry |
| t06_idempotent_payment | duplicate "Pay" requests with one idempotency key | check-then-insert race; `ON CONFLICT` visibility |
| t07_node_drain | drain storage nodes; every shard keeps an active replica | multi-group write skew and lock-order deadlocks |
| t08_expense_endpoints | approve, edit amount and change budget, all concurrently; schema fixed | write skew across several endpoints |
| t09_room_rules | book, reschedule (across days), cancel; no overlap and at most 3 bookings per room per UTC day | phantoms and per-day counts across two days |
| t10_room_rules_scaled | t09 plus: requests for different rooms, or different days of one room, must never wait for each other | as t09; locking the whole room also fails |

Models may use any technique a real engineer could: isolation levels, row or advisory locks, constraints and indexes added in an optional `migrate()` function (except t08), and bounded retries. Each task folder holds the exact prompt (`task.md`), schema (`setup.sql`), scenarios and checks (`spec.yaml`), a reference solution, the deliberately wrong variants, and internal notes (`NOTES.md`).

## 5. Setup and run instructions

Requirements: Docker (with Compose) and `make`, or PowerShell on Windows (`.\run.ps1` has the same commands; if scripts are blocked, run `powershell -ExecutionPolicy Bypass -File .\run.ps1 <command>`). Everything runs in containers: `postgres:16.15-bookworm` and `python:3.12.16-slim-bookworm`, with every Python package pinned in [requirements.txt](requirements.txt) (psycopg 3.3.6).

The commands below were run from a fresh clone of this repository in a new folder, with the eval image deleted first. Times are from that machine (Docker Desktop on Windows 11).

| step | command (Linux/macOS) | Windows | time | cost |
|---|---|---|---|---|
| copy the env template | `cp .env.example .env` | `copy .env.example .env` | - | - |
| build the eval image | `make build` | `.\run.ps1 build` | 25 s (base images already downloaded; their first download not measured) | $0 |
| start Postgres | `make up` | `.\run.ps1 up` | 2 s | $0 |
| validate one task | `make validate TASK=t01_flash_sale` | `.\run.ps1 validate -Task t01_flash_sale` | t01: 30 s, t03: 7 min (the slowest task) | $0 |
| validate everything | `make validate` | `.\run.ps1 validate` | 21 min | $0 |
| whole pipeline, mock model | `make dry-run` | `.\run.ps1 dry-run` | about 6 min | $0, no key |
| unit tests (173) | `make test` | `.\run.ps1 test` | about 2 min | $0 |
| submission zip | `make zip` | `.\run.ps1 zip` | 4 s | $0 |

Without `make build` first, the first command that needs the image prints `pull access denied for lastseat-eval` and then builds it; the warning is harmless.

- **`make validate`** grades every reference and wrong variant and writes [results/validation.md](results/validation.md) (with `TASK=`, `results/validation_partial.md`). It overwrites the committed verdicts in `results/validation/`, so `git diff results/validation` is a reproduction check: on our clean-clone run only the `seconds` fields changed.
- **`make dry-run`** runs the free model set (2 models × 10 tasks) with a mock model that returns each task's reference, grades all 20 answers and writes `results/<timestamp>-dry/` (gitignored). Every cell should pass.
- **`make zip`** builds `lastseat-eval.zip` from the committed tree (`git archive HEAD`; it refuses uncommitted changes) and checks it: under 50 MB, `README.md` at the root, no `.env`, caches or videos, no key-shaped text, and no file containing the value of any `*KEY*`/`*TOKEN*`/`*SECRET*` environment variable.

**Environment variables** (template in [.env.example](.env.example); only needed for model runs): `OPENROUTER_API_KEY`, `LASTSEAT_MAX_COST_USD`. `.env` is gitignored and never baked into the image.

**Model runs.** A run never starts implicitly: an unfinished run is resumed only with `RUN=<id>` / `-Run <id>`, and a new one starts only with `NEW=1` / `-New`.

| route | command | needs |
|---|---|---|
| OpenRouter, free models | `make run CONFIG=free TRIALS=3 NEW=1 YES=1` (`.\run.ps1 run -Config free -Trials 3 -New -Yes`) | `OPENROUTER_API_KEY`; `LASTSEAT_MAX_COST_USD` empty or `0`. A free run refuses anything else, checks every listed price is 0, and sends `max_price: 0` with every request. |
| OpenRouter, paid models | `make run CONFIG=paid NEW=1 YES=1` | `OPENROUTER_API_KEY` and `LASTSEAT_MAX_COST_USD` > 0 (hard stop). The IDs in [config/models.yaml](config/models.yaml) are a proposal, marked `confirmed: false`, and were never run. |
| Claude Code headless | `.\run.ps1 official-cli -Model claude-opus-5-5 -New -Trials 3 -Yes` | Claude Code logged in with a claude.ai account; no API key is read |
| Gemini via Antigravity CLI | `.\run.ps1 official-cli -Cli antigravity -Model gemini-3.8-flash-high -New -Trials 3 -Yes` | `agy` signed in with a Google account |

The official-CLI route is wired in `run.ps1` only. On Linux/macOS run its three steps by hand: `python -m lastseat.official_cli prepare ...` (in Docker), `python lastseat/cli_host.py results/<run>` (on the host, standard library only), `python -m lastseat.official_cli grade results/<run>` (in Docker).

A run's `summary.md` is written by `make summary RUN=<run id>` (`.\run.ps1 summary -Run <run id>`); `REGRADE=1` / `-Regrade` grades the saved answers again from disk with no API calls. The tables in this README are generated from `results/` by `python -m lastseat.report --write`.

**Recorded runtime and cost of the final runs:**

<!-- BEGIN report:runtime -->
| model | new calls in the final run (reused pilot trials excluded) | model time per answer (median s) | grading time (total s)¹ | schedules explored | scenarios not exhaustive | spent (USD) |
|---|---|---|---|---|---|---|
| `claude-opus-5-5` | 15 | 18 | 1258 | 40436 | 5 of 144 | 0.00 |
| `claude-sonnet-5-5` | 30 | 12 | 1458 | 49127 | 7 of 144 | 0.00 |
| `claude-haiku-5-5` | 30 | 25 | 1279 | 36530 | 4 of 144 | 0.00 |
| `gemini-3.8-flash-high` | 19 | 335 | 576 | 17570 | 0 of 132 | 0.00 |
| `cohere/north-mini-code:free` | 30 | 104 | 413 | 11201 | 0 of 73 | 0.00 |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 30 | 119 | 1812 | 49834 | 14 of 109 | 0.00 |

Grader validation (`make validate`, 53 solutions): 21 min of grading time¹ on the machine that produced these results (sum of per-solution times; Docker Desktop on Windows 11).

¹ Times of the first grade, run one solution at a time (each run's grading right after its model calls; validation with `make validate`). This is the estimate for a reproduction. Some runs were later re-graded from disk with 4 grading jobs in parallel, which is slower per solution because the jobs compete for the machine: `claude-opus-5-5` 1713 s, `claude-sonnet-5-5` 2096 s, `claude-haiku-5-5` 1549 s, `gemini-3.8-flash-high` 739 s, `nvidia/nemotron-3-ultra-550b-a55b:free` 2373 s, validation 30 min. Schedules and scores were identical; they do not depend on timing.
<!-- END report:runtime -->

The OpenRouter free tier allowed 50 requests per day (UTC) on this account ([config/models.free.yaml](config/models.free.yaml)), so one free model's 30 calls fit in one day.

## 6. Models tested and results

<!-- BEGIN report:models -->
| model (exact ID) | route | settings | trials | run dates (UTC) | cells graded | run |
|---|---|---|---|---|---|---|
| `claude-opus-5-5` | Claude Code `claude -p` 2.1.319, claude.ai Pro login | effort `high`, no tools (`--tools ''`), CLI system prompt included | 3 per task | 2026-11-07 | 30/30 (15 reused from pilots) | [`final-claude-opus-5-5-cli`](results/final-claude-opus-5-5-cli/summary.md) |
| `claude-sonnet-5-5` | Claude Code `claude -p` 2.1.319, claude.ai Pro login | effort `high`, no tools (`--tools ''`), CLI system prompt included | 3 per task | 2026-11-07 | 30/30 | [`final-claude-sonnet-5-5-cli`](results/final-claude-sonnet-5-5-cli/summary.md) |
| `claude-haiku-5-5` | Claude Code `claude -p` 2.1.319, claude.ai Pro login | effort `high`, no tools (`--tools ''`), CLI system prompt included | 3 per task | 2026-11-07 | 30/30 | [`final-claude-haiku-5-5-cli`](results/final-claude-haiku-5-5-cli/summary.md) |
| `gemini-3.8-flash-high` | Antigravity CLI `agy --print` 1.5.3, Google sign-in | `-high` variant chosen by model id, every tool action denied, CLI system prompt included | 3 per task | 2026-11-07 | 30/30 (12 reused from pilots) | [`final-gemini-3.8-flash-high-cli`](results/final-gemini-3.8-flash-high-cli/summary.md) |
| `cohere/north-mini-code:free` | OpenRouter free tier (served by Cohere) | reasoning effort `high`, max_tokens 32000, max_price 0 | 3 per task | 2026-11-08 | 30/30 | [`final-free-north-mini-code`](results/final-free-north-mini-code/summary.md) |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | OpenRouter free tier (served by Nvidia) | reasoning effort `high`, max_tokens 32000, max_price 0 | 3 per task | 2026-11-07 | 30/30 | [`final-free-nemotron-3-ultra`](results/final-free-nemotron-3-ultra/summary.md) |
<!-- END report:models -->

**Settings.** Every model gets the same prompt: the shared contract ([lastseat/prompts/contract.md](lastseat/prompts/contract.md)) followed by the task's `task.md`.

- **OpenRouter API route:** `max_tokens` 32000, `reasoning: {effort: high}`, and `provider.max_price` 0. Temperature is not sent, so the provider default applies ([config/models.free.yaml](config/models.free.yaml)); the exact request body is saved per trial as `request.json`.
- **Official CLI route:** Claude models ran through Claude Code headless (`claude -p` 2.1.319, `--effort high`, all tools disabled with `--tools ''`). Gemini ran through Antigravity CLI (`agy --print` 1.5.3); the `-high` variant is chosen by the model ID, and every tool action is denied. Temperature and max tokens were not set, so the CLI defaults apply. Each run's exact command is in its `run_meta.json`.
- **CLI caveat:** both CLIs put their own agent system prompt before ours (Antigravity's is about 8.5k input tokens), so CLI cells and API cells are not directly comparable.
- Where a final run reuses pilot trials (Opus 15, Gemini 12), the model, CLI, effort and prompt were identical, and the reused answers were graded again by the final grader. Each run's `summary.md` lists them.

**Results per task** (trials passed out of 3; ✅ = pass^3, all three trials passed):

<!-- BEGIN report:results -->
**official CLI route**

| task | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` | `gemini-3.8-flash-high` |
|---|---|---|---|---|
| t01_flash_sale | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ |
| t02_on_call | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ |
| t03_expense_budget | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ |
| t04_room_booking | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ |
| t05_wallet_transfer | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ |
| t06_idempotent_payment | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ |
| t07_node_drain | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ |
| t08_expense_endpoints | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ |
| t09_room_rules | 3/3 ✅ | 3/3 ✅ | 2/3 ❌ | 3/3 ✅ |
| t10_room_rules_scaled | 3/3 ✅ | 3/3 ✅ | 3/3 ✅ | 2/3 ❌ |
| **trials passed** | 30/30 | 30/30 | 29/30 | 29/30 |
| **mean score** | 1.000 | 1.000 | 0.983 | 0.967 |
| **tasks with pass^3** | 10/10 | 10/10 | 9/10 | 9/10 |
| **latent_api_error warnings** | 0 | 0 | 0 | 4 |

**OpenRouter API route**

| task | `cohere/north-mini-code:free` | `nvidia/nemotron-3-ultra-550b-a55b:free` |
|---|---|---|
| t01_flash_sale | 2/3 ❌ | 3/3 ✅ |
| t02_on_call | 2/3 ❌ | 3/3 ✅ |
| t03_expense_budget | 0/3 ❌ | 3/3 ✅ |
| t04_room_booking | 2/3 ❌ | 0/3 ❌ |
| t05_wallet_transfer | 3/3 ✅ | 3/3 ✅ |
| t06_idempotent_payment | 1/3 ❌ | 2/3 ❌ |
| t07_node_drain | 1/3 ❌ | 1/3 ❌ |
| t08_expense_endpoints | 3/3 ✅ | 3/3 ✅ |
| t09_room_rules | 0/3 ❌ | 1/3 ❌ |
| t10_room_rules_scaled | 0/3 ❌ | 1/3 ❌ |
| **trials passed** | 14/30 | 20/30 |
| **mean score** | 0.575 | 0.700 |
| **tasks with pass^3** | 2/10 | 5/10 |
| **latent_api_error warnings** | 0 | 0 |
<!-- END report:results -->

`latent_api_error` is a static warning that never changes a score: the solution names a `psycopg.errors` class that the pinned psycopg does not define, which crashes only if that line ever runs (section 8).

**Failure categories per model** (definitions in section 7):

<!-- BEGIN report:categories -->
| model | route | failed trials | load | spec | concurrency | harness | load reasons |
|---|---|---|---|---|---|---|---|
| `claude-opus-5-5` | official CLI (Claude Code) | 0 | 0 | 0 | 0 | 0 | - |
| `claude-sonnet-5-5` | official CLI (Claude Code) | 0 | 0 | 0 | 0 | 0 | - |
| `claude-haiku-5-5` | official CLI (Claude Code) | 1 | 0 | 1 | 0 | 0 | - |
| `gemini-3.8-flash-high` | official CLI (Antigravity) | 1 | 1 | 0 | 0 | 0 | `exec_error` 1 |
| `cohere/north-mini-code:free` | OpenRouter API (free tier) | 16 | 11 | 1 | 4 | 0 | `migrate_error` 4, `no_code` 4, `syntax_error` 2, `exec_error` 1 |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | OpenRouter API (free tier) | 10 | 7 | 3 | 0 | 0 | `migrate_error` 6, `forbidden_import` 1 |
<!-- END report:categories -->

Per-trial scores, failure details and API records are in each run's `summary.md` (linked in the models table).

## 7. Grader and validation

**How a solution is run.** Each request runs on its own Postgres connection and pauses before every `db` call (`begin`, `execute`, `commit`, `rollback`). The scheduler lets one request take one step at a time. A request is BLOCKED when `pg_blocking_pids()` shows it waiting for another's lock; this is never inferred from timing. Interleavings are explored with a stateless depth-first search, re-running each schedule from a fresh copy of the database. The cap is 2000 depth-first schedules per scenario, plus 200 seeded-random ones beyond it; every scenario records whether its search was exhaustive. Each request may make at most 60 `db` calls, so an endless retry loop fails liveness. The database runs with `deadlock_timeout=50ms` and `autovacuum=off` for determinism. Its durability settings are off, which affects crash safety only, not locking or MVCC.

**Scoring per trial.**

| component | weight | passes when |
|---|---|---|
| safety | 0.5 | every invariant holds after every explored schedule of every concurrent scenario, **and** at least one solo check that expects the operation to succeed passed |
| solo correctness | 0.25 | every single-request check passes (return value and resulting database state) |
| liveness | 0.25 | in `must_all_succeed` scenarios every request succeeds in every schedule (no exception, no step limit); in `must_not_block` scenarios (t10) no request ever waits for another request's lock |

A trial **passes** only with all three. The second half of the safety rule is the *vacuous-safety* rule: code that never performs the operation cannot break an invariant, and was scored 0.5 for doing nothing in the pilot (Nemotron's t07 raised a syntax error on every call). The rule is deliberately narrow. Safety is withheld only when no success-path solo check passed, not whenever any solo check fails, so a genuinely safe solution that misses one edge case keeps its safety score.

**Failure categories** (one per failed trial):

- **load**: never graded: syntax error, forbidden import, missing function, `migrate()` failed (`migrate_error`), `migrate()` defined where the task forbids it (`forbidden_migrate`), or no code in the answer.
- **spec**: a logic bug that shows without concurrency: a solo check failed, or a *serial* schedule broke an invariant or liveness.
- **concurrency**: correct alone and in every serial order, but some interleaved schedule broke an invariant, or made a valid request fail or wait.
- **harness**: the grader itself failed (none in the final runs).

A serial schedule runs one request completely before the next starts. The grader finds serial schedules among the explored ones: a schedule is serial when each request's steps form one unbroken block. Every scenario has two requests, so there are two serial orders. An exhaustive search contains both. When a search is capped and misses one, that order is run separately; it decides the category only and is not counted in schedules or scores.

**Validation.** Every task ships a reference solution that must pass and at least two deliberately wrong variants. Each variant declares (`EXPECT:` in its docstring) exactly which components it must fail, and `make validate` checks the match exactly. Every failing schedule must reproduce on re-run.

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

All 53 validated solutions were searched exhaustively: 34,071 schedules in total, with 86 saved counterexamples. Of the 43 wrong variants, 40 fail only under concurrency. The other three fail without it: t04 `w5_closed_range_constraint` and t06 `w2_on_conflict_no_reread` fail a solo check (category spec), and t08 `w5_running_total_column` is refused before grading (`forbidden_migrate`).

**Determinism and reproduction checks.**

- Every failing schedule is re-run from its recorded choices and must produce the same trace fingerprint. All 234 verdicts in the final runs and the validation suite are marked reproducible: 180 final trials, 53 validated solutions, and the t10 alternative.
- A fresh clone, with the image rebuilt from the Dockerfile, reproduced the t01 and t03 validation: `git diff` of the 10 verdict files showed only the `seconds` fields changed. The mock-model dry run passed 20/20.
- When the category rule changed on 2026-11-08, every run was graded again from disk with no API calls; no score changed ([docs/AI_USE.md](docs/AI_USE.md)).

## 8. Failure analysis

The notable failures, grouped by what went wrong. Every failed final-run trial is listed with its files at the end of this section.

### Cohere North Mini Code: the only race conditions in the final runs (4 trials)

Each of these four solutions passes every solo check and both serial orders. They fail only when the two requests overlap, and every failing trace reproduces.

**t03 trials 2 and 3: a stale snapshot under REPEATABLE READ (safety, category concurrency).** Both solutions open a REPEATABLE READ transaction and lock the department row with `FOR UPDATE`, then compare `SUM(amount)` of approved expenses with the budget. Trial 2 locks the expense row first and then the department row; trial 3 locks both in one `JOIN … FOR UPDATE`. The lock does not refresh the snapshot. Under REPEATABLE READ the snapshot is fixed by the transaction's first statement. When the second approval gets the lock after the first commits, it still sums the approved expenses as of its old snapshot, sees 0, and approves. The budget is 100 and the two expenses are 60 and 50, so both approve and the total reaches 110. Postgres raises no serialization error, because the first approval only locked the department row and never changed it, so the retry loop never runs. This is the same mistake as the wrong variant `w3_department_lock_repeatable_read`. Unsafe in 134 of 148 schedules (trial 2) and 24 of 36 (trial 3), per scenario. Shortest traces: [trial 2](results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_2/counterexample_1.txt) (12 steps), [trial 3](results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_3/counterexample_1.txt) (10 steps).

**t01 trial 1 and t02 trial 2: SQLSTATE 40001 with no retry (liveness, category concurrency).** Neither request hangs; there is no deadlock and no step limit. Postgres raises a serialization failure in the middle of a request that should succeed, and the code lets it escape.

- **t01:** REPEATABLE READ plus `SELECT stock … FOR UPDATE`. If the other buyer commits while this request waits for the row lock, Postgres raises "could not serialize access due to concurrent update", because the row changed after this transaction's snapshot. With 6 in stock and two purchases of 3, both must succeed; one raises instead. This is the same mistake as `w2_repeatable_read_no_retry`. It fails in 24 of 36 schedules. [Trace](results/final-free-north-mini-code/north-mini-code/t01_flash_sale/trial_1/counterexample_2.txt), 7 steps.
- **t02:** SERIALIZABLE plus `FOR UPDATE` on the shift's on-call doctors, and it re-raises every exception. With three doctors on call, two may leave; the second gets 40001 instead ([trace](results/final-free-north-mini-code/north-mini-code/t02_on_call/trial_2/counterexample_1.txt)). It also fails when the two doctors are in *different* shifts ([trace](results/final-free-north-mini-code/north-mini-code/t02_on_call/trial_2/counterexample_3.txt): "read/write dependencies among transactions"). On a table this small, SERIALIZABLE's read tracking is coarse, so unrelated requests can conflict. That is normal SSI behaviour, and the reason SERIALIZABLE code needs a retry loop. This is the same mistake as `w3_serializable_no_retry`. It fails in 80 of 92 and 240 of 252 schedules.

### Code that did not run on the real stack

- **`tsrange` on `timestamptz` columns (Nemotron t04 ×3, t09 trial 2, t10 trial 1; Cohere t04 trial 1).** The schema stores `starts_at`/`ends_at` as `timestamptz`. These solutions build an exclusion constraint with `tsrange(starts_at, ends_at)`, which takes `timestamp` without a time zone. Postgres finds no matching function, so `migrate()` fails: `function tsrange(timestamp with time zone, timestamp with time zone) does not exist`. The reference uses `tstzrange`. The idea (an exclusion constraint) is right, but the solution never got past setting up its database. [Example verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t04_room_booking/trial_1/verdict.json).
- **Other `migrate()` errors.**
  - `ALTER TABLE … ADD CONSTRAINT IF NOT EXISTS` (Nemotron t06 trial 2); Postgres has no such syntax.
  - `CREATE INDEX CONCURRENTLY` inside a transaction (Cohere t06 trial 3).
  - `EXCLUSION USING GIST` instead of `EXCLUDE` (Cohere t10 trial 1).
  - A syntax error near `)` (Cohere t10 trial 2).
- **Answers with no code (Cohere ×4).** Three hit the 32,000-token output limit while still reasoning (`finish_reason: length`); one stopped with no Python block.
- **psycopg2 exception names in psycopg 3 code (Gemini, 1 failure and 3 latent).** The contract says errors are `psycopg.errors.*` (psycopg 3). Gemini wrote `psycopg.errors.TransactionRollbackError`, a psycopg2 name that psycopg 3.3.6's `errors` module does not define.
  - In t10 trial 2 the name sits in a module-level tuple, so loading the solution raised `AttributeError` (category load). [Verdict](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t10_room_rules_scaled/trial_2/verdict.json).
  - In t01 trials 2 and 3 and t08 trial 2 the name is inside an `except (...)` clause. Python looks it up only when an exception reaches that clause, and in no explored schedule did one, so these trials **passed** with a crash waiting in their retry path. A static check now flags them as `latent_api_error` without changing the score ([t08 trial 2](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t08_expense_endpoints/trial_2/solution.py)).
  - In t02 trial 3 Gemini wrote `getattr(errors, "TransactionRollbackError", ())`, which tolerates the missing name.

### Logic bugs that show without concurrency (category spec)

- **Haiku t09 trial 1: an off-by-one on reschedule.** The task says of a rescheduled booking: "Its old time does not count against it, so it may move within the same day or overlap its own old slot." Haiku correctly excludes the booking's own id from the day's count, but then refuses when `count >= MAX_PER_DAY - 1`, subtracting the booking a second time. A valid move within a day that already holds 3 bookings (this one included) is refused. It fails the solo check "a booking moves within a full day", and liveness in two "both fit" scenarios, in serial orders as well as interleaved ones. [Solution](results/final-claude-haiku-5-5-cli/claude-haiku-5-5/t09_room_rules/trial_1/solution.py), [trace](results/final-claude-haiku-5-5-cli/claude-haiku-5-5/t09_room_rules/trial_1/counterexample_1.txt).
- **Nemotron t10 trial 3: a counter table without a backfill.** `migrate()` creates a `room_day_counts` table to count bookings per room and day, but never fills it from the bookings already in the database. The counter starts at 0, so a fourth booking on a day that already has 3 is accepted even when run alone. Three solo checks fail, and both serial orders break the 3-per-day rule (2 of 2) in three scenarios. This is a logic bug, not a race: it fails without any concurrency. [Solution](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_3/solution.py), [trace](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_3/counterexample_1.txt).
- **The UTC day (Nemotron t09 trial 1, Cohere t09 trial 3).** Both fail the solo check "the day is the UTC day, whatever offset the time is given in": a booking given with a +05:30 offset that falls on a full UTC day is accepted.

### Over-locking on t09, per-day locking on t10

The rules in t09 are per room *and* day. Yet every one of the 12 passing final-run t09 answers locked the whole room, through the `rooms` row (`FOR UPDATE` / `FOR NO KEY UPDATE`) or an advisory lock keyed on the room alone. Those 12 answers are Opus 3, Sonnet 3, Haiku 2, Gemini 3 and Nemotron 1. Locking the whole room is safe and live, but it makes bookings for different days of one room wait for each other. t09 cannot tell it apart from the reference, so t10 repeats t09 with one added requirement: "Requests that affect different rooms, or different days of the same room, must never wait for each other." Its `must_not_block` scenarios fail any schedule in which one request waits for another's lock.

On t10 all 12 passing answers locked per room and day:
- Opus 3, Sonnet 3, Haiku 3 and Gemini 2 used advisory locks keyed on (room, day);
- Nemotron 1 locked a counter row per (room, day).

None of them waited in any explored schedule. The wrong variant `w5_whole_room_lock`, which uses the t09 strategy, is blocked in 24/36, 46/74 and 40/67 schedules of the three same-room scenarios. In these runs the models locked coarsely when allowed and per day when told to.

### A race seen only in an extra pilot run (not a final result)

<!-- BEGIN report:pilot_concurrency -->
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t03_expense_budget · run `20261107T001717Z` (extra pilot run, not part of the final results): **concurrency**; 14/24 schedules unsafe in "nothing approved yet, two approvals that do not both fit", 0 of 2 serial; 14/24 schedules unsafe in "one already approved, two approvals that do not both fit", 0 of 2 serial — [verdict](results/20261107T001717Z/nemotron-3-ultra/t03_expense_budget/trial_1/verdict.json), [counterexample 1](results/20261107T001717Z/nemotron-3-ultra/t03_expense_budget/trial_1/counterexample_1.txt), [counterexample 2](results/20261107T001717Z/nemotron-3-ultra/t03_expense_budget/trial_1/counterexample_2.txt)
  - All attempts by this model on t03_expense_budget: 5 (`20261106T123821Z`, `20261107T001717Z`, `final-free-nemotron-3-ultra`), 1 failed.
<!-- END report:pilot_concurrency -->

This run was started by accident and kept by decision (see the note in its [summary](results/20261107T001717Z/summary.md)); it is **not** counted in any final result. Nemotron's `approve_expense` locks the department row (`FOR UPDATE OF d`) in the same statement that reads the approved total through a `SUM` subquery. Under READ COMMITTED, the second approval waits on that lock. When the first commits, Postgres re-checks only the locked department row; the `SUM` subquery keeps the statement's original snapshot, so the second approval still sees 0 approved, and both commit. It is the same failure as Cohere's t03, reached through READ COMMITTED's re-check instead of a REPEATABLE READ snapshot.

### Every failed final-run trial

<!-- BEGIN report:failures -->
- `claude-haiku-5-5` · t09_room_rules · trial_1: **spec** — [verdict](results/final-claude-haiku-5-5-cli/claude-haiku-5-5/t09_room_rules/trial_1/verdict.json), [counterexample 1](results/final-claude-haiku-5-5-cli/claude-haiku-5-5/t09_room_rules/trial_1/counterexample_1.txt), [counterexample 2](results/final-claude-haiku-5-5-cli/claude-haiku-5-5/t09_room_rules/trial_1/counterexample_2.txt), [counterexample 3](results/final-claude-haiku-5-5-cli/claude-haiku-5-5/t09_room_rules/trial_1/counterexample_3.txt)
- `gemini-3.8-flash-high` · t10_room_rules_scaled · trial_2: **load** (exec_error): `AttributeError: module 'psycopg.errors' has no attribute 'TransactionRollbackError'` — [verdict](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t10_room_rules_scaled/trial_2/verdict.json)
- `cohere/north-mini-code:free` · t01_flash_sale · trial_1: **concurrency** — [verdict](results/final-free-north-mini-code/north-mini-code/t01_flash_sale/trial_1/verdict.json), [counterexample 1](results/final-free-north-mini-code/north-mini-code/t01_flash_sale/trial_1/counterexample_1.txt), [counterexample 2](results/final-free-north-mini-code/north-mini-code/t01_flash_sale/trial_1/counterexample_2.txt)
- `cohere/north-mini-code:free` · t02_on_call · trial_2: **concurrency** — [verdict](results/final-free-north-mini-code/north-mini-code/t02_on_call/trial_2/verdict.json), [counterexample 1](results/final-free-north-mini-code/north-mini-code/t02_on_call/trial_2/counterexample_1.txt), [counterexample 2](results/final-free-north-mini-code/north-mini-code/t02_on_call/trial_2/counterexample_2.txt), [counterexample 3](results/final-free-north-mini-code/north-mini-code/t02_on_call/trial_2/counterexample_3.txt)
- `cohere/north-mini-code:free` · t03_expense_budget · trial_1: **load** (syntax_error): `line 65: '[' was never closed` — [verdict](results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_1/verdict.json)
- `cohere/north-mini-code:free` · t03_expense_budget · trial_2: **concurrency** — [verdict](results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_2/verdict.json), [counterexample 1](results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_2/counterexample_1.txt), [counterexample 2](results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_2/counterexample_2.txt)
- `cohere/north-mini-code:free` · t03_expense_budget · trial_3: **concurrency** — [verdict](results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_3/verdict.json), [counterexample 1](results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_3/counterexample_1.txt), [counterexample 2](results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_3/counterexample_2.txt)
- `cohere/north-mini-code:free` · t04_room_booking · trial_1: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist` — [verdict](results/final-free-north-mini-code/north-mini-code/t04_room_booking/trial_1/verdict.json)
- `cohere/north-mini-code:free` · t06_idempotent_payment · trial_2: **load** (syntax_error): `line 9: expected ':'` — [verdict](results/final-free-north-mini-code/north-mini-code/t06_idempotent_payment/trial_2/verdict.json)
- `cohere/north-mini-code:free` · t06_idempotent_payment · trial_3: **load** (migrate_error): `ActiveSqlTransaction: CREATE INDEX CONCURRENTLY cannot run inside a transaction block` — [verdict](results/final-free-north-mini-code/north-mini-code/t06_idempotent_payment/trial_3/verdict.json)
- `cohere/north-mini-code:free` · t07_node_drain · trial_1: **load** (exec_error): `SyntaxError: from __future__ imports must occur at the beginning of the file (solution.py, line 3)` — [verdict](results/final-free-north-mini-code/north-mini-code/t07_node_drain/trial_1/verdict.json)
- `cohere/north-mini-code:free` · t07_node_drain · trial_2: **load** (no_code) — [verdict](results/final-free-north-mini-code/north-mini-code/t07_node_drain/trial_2/verdict.json)
- `cohere/north-mini-code:free` · t09_room_rules · trial_1: **load** (no_code) — [verdict](results/final-free-north-mini-code/north-mini-code/t09_room_rules/trial_1/verdict.json)
- `cohere/north-mini-code:free` · t09_room_rules · trial_2: **load** (no_code) — [verdict](results/final-free-north-mini-code/north-mini-code/t09_room_rules/trial_2/verdict.json)
- `cohere/north-mini-code:free` · t09_room_rules · trial_3: **spec** — [verdict](results/final-free-north-mini-code/north-mini-code/t09_room_rules/trial_3/verdict.json), [counterexample 1](results/final-free-north-mini-code/north-mini-code/t09_room_rules/trial_3/counterexample_1.txt)
- `cohere/north-mini-code:free` · t10_room_rules_scaled · trial_1: **load** (migrate_error): `SyntaxError: syntax error at or near "EXCLUSION"` — [verdict](results/final-free-north-mini-code/north-mini-code/t10_room_rules_scaled/trial_1/verdict.json)
- `cohere/north-mini-code:free` · t10_room_rules_scaled · trial_2: **load** (migrate_error): `SyntaxError: syntax error at or near ")"` — [verdict](results/final-free-north-mini-code/north-mini-code/t10_room_rules_scaled/trial_2/verdict.json)
- `cohere/north-mini-code:free` · t10_room_rules_scaled · trial_3: **load** (no_code) — [verdict](results/final-free-north-mini-code/north-mini-code/t10_room_rules_scaled/trial_3/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t04_room_booking · trial_1: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t04_room_booking/trial_1/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t04_room_booking · trial_2: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t04_room_booking/trial_2/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t04_room_booking · trial_3: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t04_room_booking/trial_3/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t06_idempotent_payment · trial_2: **load** (migrate_error): `SyntaxError: syntax error at or near "NOT"` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t06_idempotent_payment/trial_2/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t07_node_drain · trial_1: **load** (forbidden_import): `collections` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_1/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t07_node_drain · trial_3: **spec** (vacuous_safety) — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/verdict.json), [counterexample 1](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/counterexample_1.txt), [counterexample 2](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/counterexample_2.txt), [counterexample 3](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/counterexample_3.txt)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t09_room_rules · trial_1: **spec** — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t09_room_rules/trial_1/verdict.json), [counterexample 1](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t09_room_rules/trial_1/counterexample_1.txt)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t09_room_rules · trial_2: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone, unknown) does not exis…` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t09_room_rules/trial_2/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t10_room_rules_scaled · trial_1: **load** (migrate_error): `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist` — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_1/verdict.json)
- `nvidia/nemotron-3-ultra-550b-a55b:free` · t10_room_rules_scaled · trial_3: **spec** — [verdict](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_3/verdict.json), [counterexample 1](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_3/counterexample_1.txt), [counterexample 2](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_3/counterexample_2.txt), [counterexample 3](results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_3/counterexample_3.txt)

Warnings (not scored):

- `gemini-3.8-flash-high` · t01_flash_sale · trial_2: `latent_api_error` `psycopg.errors.TransactionRollbackError` (line 27) — [solution](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t01_flash_sale/trial_2/solution.py)
- `gemini-3.8-flash-high` · t01_flash_sale · trial_3: `latent_api_error` `psycopg.errors.TransactionRollbackError` (line 33) — [solution](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t01_flash_sale/trial_3/solution.py)
- `gemini-3.8-flash-high` · t08_expense_endpoints · trial_2: `latent_api_error` `psycopg.errors.TransactionRollbackError` (line 53, 113, 154) — [solution](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t08_expense_endpoints/trial_2/solution.py)
- `gemini-3.8-flash-high` · t10_room_rules_scaled · trial_2: `latent_api_error` `psycopg.errors.TransactionRollbackError` (line 8) — [solution](results/final-gemini-3.8-flash-high-cli/gemini-3.8-flash-high/t10_room_rules_scaled/trial_2/solution.py)
<!-- END report:failures -->

## 9. Main failure mode and hot take

**In these tasks and runs, the frontier models wrote no race conditions.** Opus 5.5, Sonnet 5.5, Haiku 5.5 and Gemini 3.8 Flash (high) had 0 concurrency failures in 120 final trials, and none in their pilot runs. When t10 asked for finer locking, every passing answer locked per room and day.

**The gap that remains is executing on the real stack.** Of the 28 failed final trials, 19 never got graded:

- 10 were rejected by Postgres while setting up the schema (`migrate_error`);
- 4 contained no code;
- 5 failed to load as Python (syntax errors, a forbidden import, or a name that does not exist).

The two frontier failures were not races either:
- **Gemini:** an exception name from the wrong library version, which also sits unexecuted in three trials that passed.
- **Haiku:** a misread of one sentence in the spec.

Only Cohere's code failed because of true concurrency.

**Why this matters for how such code is checked.** Several of these mistakes read as correct: `tsrange` looks like the right function, `TransactionRollbackError` is a real name in psycopg2, and a REPEATABLE READ transaction that takes `FOR UPDATE` looks like it is guarding the budget. Running the code against the real database decided each one in seconds. We did not test code review or LLM judges on these solutions, so this is an argument, not a measurement: a review that reads the code without running it would have to know the Postgres function signatures, the psycopg version and the snapshot rules to catch them.

## 10. Limitations

- **Small sample.** 10 tasks (t09 and t10 share a schema and rules) with 3 trials each; pass^3 is a coarse reliability measure, and one trial changes a model's pass rate by 3.3 points.
- **CLI routing for the frontier models.** The Claude models ran through Claude Code headless and Gemini through Antigravity CLI, both with their own system prompt before ours and with no control over temperature or max tokens. Their cells are not directly comparable with the API cells.
- **The Gemini model tested is Gemini 3.8 Flash at its highest listed effort (`gemini-3.8-flash-high`).** On the account used (a Google AI Pro sign-in), `agy models` in Antigravity CLI 1.5.3 lists Gemini 3.8 Flash at high, medium and low effort and no other Gemini model (checked 2026-11-08). No larger Gemini model was available through this route, so none was tested.
- **No GPT model was tested.** The paid route exists in the code, but a paid run was never made.
- **Antigravity's built-in web search cannot be denied.** In one Gemini call (t04 trial 2) the model ran `search_web`; the harness stopped, never graded that answer, and asked again with unchanged settings (recorded in that run's `run_meta.json`). No graded answer ran any tool.
- **Free models via OpenRouter** come with the free tier's daily request cap and whatever upstream provider OpenRouter routes to (recorded per trial). Their results reflect the free endpoints on the run dates.
- **Possible prompt contamination.** The task prompts were sent to third-party free endpoints, which may retain them; a future model could have seen them.
- **Statement-level interleavings.** The scheduler switches between requests only at `db` call boundaries (plus the lock waits Postgres reports). A PL/pgSQL function or a single multi-row statement is one step. Every scenario has two requests and small seed data. Where the 2000-schedule cap is reached, 200 seeded-random schedules are added and the scenario is marked not exhaustive (counted in section 5).
- **No parallelism scoring beyond `must_not_block`.** A solution that serializes more than needed passes every task except t10. A retry-heavy solution can also pass t10: the SERIALIZABLE + bounded-retry alternative never waits, but in most of its schedules it hits serialization failures and retries.
- **One machine, one Postgres version** (16.15). Other databases and isolation implementations are not covered.

## 11. Prior work and sources

- **Jepsen** (Kyle Kingsbury), black-box testing of distributed databases under faults: <https://jepsen.io>. **Elle**: K. Kingsbury, P. Alvaro, "Elle: Inferring Isolation Anomalies from Experimental Observations", PVLDB 14(3), 2020. Jepsen and Elle test the *database*; LastSeat holds the database fixed and tests the *application code* a model writes against it.
- H. Berenson, P. Bernstein, J. Gray, J. Melton, E. O'Neil, P. O'Neil, "A Critique of ANSI SQL Isolation Levels", SIGMOD 1995: the anomaly vocabulary (lost update, write skew, phantom) used to design the tasks.
- **PostgreSQL 16 documentation, Transaction Isolation**: <https://www.postgresql.org/docs/16/transaction-iso.html>, and the SERIALIZABLE (SSI) and explicit locking chapters. In particular, the READ COMMITTED re-check: an `UPDATE`, `DELETE` or `SELECT … FOR UPDATE` that waits for a concurrent writer re-evaluates its `WHERE` clause against the newest row version once that writer commits. This is why t01's single conditional `UPDATE` is safe, why a read followed by a separate write is not, and why the Nemotron t03 pilot's `SUM` subquery stayed stale.
- M. Kleppmann, *Designing Data-Intensive Applications*, O'Reilly 2017, ch. 7: the doctors-on-call write-skew example that t02 follows (t03 is its non-textbook twin, where locking the rows you read does not help).
- **CONCUR**: J. Huang, T. Mahmud, C. Pasareanu, G. Yang, "CONCUR: Benchmarking LLMs for Concurrent Code Generation", arXiv:2603.03683, 2026. It checks LLM-written multithreaded Java with model checking. LastSeat applies the same idea, correctness under every ordering, to database transactions.
- **REFUTE**: S. Sinha, S. Goel, P. Kumaraguru, J. Geiping, M. Bethge, A. Prabhu, "Can Language Models Falsify? Evaluating Algorithmic Reasoning with Counterexample Creation", arXiv:2502.19414, 2025.
- **TestCase-Eval**: Z. Yang, Z. Kuang, X. Xia, Y. Zhao, "Can LLMs Generate High-Quality Test Cases for Algorithm Problems? TestCase-Eval: A Systematic Evaluation of Fault Coverage and Exposure", ACL 2025 (short papers), arXiv:2506.12278.
- REFUTE and TestCase-Eval judge code by a concrete failing input; here the failing input is an interleaving.

**What existed before vs. what was built during the hackathon.** Existing: PostgreSQL, psycopg, Docker, and the ideas above. Built during the hackathon: everything in this repository. That covers the scheduler and `db` API, the ten tasks with references and wrong variants, the grader and validator, the OpenRouter runner with its zero-spend guards, the official-CLI providers, the report generator and the packaging check.

## 12. AI use

**Tools.**

- **Claude Code (Claude Opus 5.5)** drafted the harness (scheduler, grader, validator, runner, CLI providers, report generator), the tasks, references and wrong variants, the tests, and this README.
- **Claude (chat)** helped with research, design review, and the video script.
- **The video** was AI-generated: slides designed with Claude (chat), video and voiceover produced with Harq AI.

The session-by-session log of what was drafted and what needed review is in [docs/AI_USE.md](docs/AI_USE.md). The rules Claude Code worked under are in [CLAUDE.md](CLAUDE.md) and [SPEC.md](SPEC.md): one milestone at a time with human review, never edit the grader or scheduler to force a result, no API keys in code or logs, and pinned versions.

**Decisions I made.** Several were proposed by Claude or Claude Code; I reviewed them, chose between options and approved them:

- **The domain.** I pivoted the project from competitive programming to Postgres concurrency, to match my backend and system-design work.
- **The vacuous-safety rule, narrow version.** After the pilot showed code that never ran scoring 0.5 for safety, I chose to withhold safety only when no success-path solo check passed. I rejected the literal "solo score 0" rule because it would also zero safety for two genuinely safe wrong variants (t04 `w5`, t06 `w2`).
- **Seed before migrate.** `migrate()` runs on a database that already holds the scenario's data, like a production migration, so a constraint must accept existing rows and a counter table must be backfilled. This is exactly what Nemotron's t10 trial 3 got wrong.
- **The t08 fixed-schema rule.** I replaced a vaguer sentence with "no `migrate()`", enforced by the grader (`forbidden_migrate`), so a running-total column cannot sidestep the locking the task tests.
- **The t09/t10 twin.** After every t09 answer so far (Nemotron ×1, Opus ×3) passed by locking the whole room, I approved adding t10 with one stated throughput requirement; the harness gained `must_not_block` to check it.
- **The serial-versus-interleaved category rule.** "Concurrency" now means correct alone and in every serial order but broken by an interleaving; anything that fails serially is a logic bug (spec). This moved one Nemotron trial (t10 trial 3) from concurrency to spec; its first verdict is kept as `verdict.prev.json`.
- **Reporting the negative result honestly.** When the frontier models passed almost everything, I kept the tasks as they were instead of hardening them until models failed.

**Reflection.** Most of the code was written by AI, so my main job was judging it. The habit that mattered most was asking “is this failure genuine?” before trusting any number: I held back paid runs until a free pilot showed real failures, and when the results came in I insisted on separating real races from code that simply didn’t run, which led to the serial-vs-interleaved rule. I also checked whether the idea already existed before committing to it, and kept the result honest when the frontier models passed almost everything, instead of tuning tasks until they failed. Without the scheduler I would not have caught most of these bugs by reading the code: tsrange on a timestamptz column, or a psycopg2 exception name in psycopg 3 code, looks correct until Postgres runs it. The biggest thing I learned is that taking a lock does not refresh what a transaction has already read: under REPEATABLE READ the snapshot is fixed, and even under READ COMMITTED a subquery computed before a lock wait stays stale. That is the bug behind both real race conditions in this eval.

**How the models were reached, at $0.** The plan was paid API access through OpenRouter, but I had no international card to buy credits. I then tried Amazon Bedrock with my existing AWS credits; the non-Anthropic models were available, but the Anthropic use-case form was refused (“account not authorized”), and support could not resolve it before the deadline. So I used the routes I already had: the free OpenRouter tier for two free models, Claude Code (my Claude Pro plan) for the Claude models, and Antigravity CLI for Gemini. I had planned to revisit paying for OpenRouter credits after the Opus pilot; once Opus (and later Sonnet) passed every task, a paid run of the same models would not have changed the finding, so I didn’t spend. The cost is the CLI caveat in section 10: the frontier models went through their CLIs, not a raw API.

## 13. Repository layout

```
lastseat-eval/
├── README.md            this file
├── SPEC.md              build spec: the source of truth for the design
├── CLAUDE.md            working rules for Claude Code
├── Makefile, run.ps1    every command (Linux/macOS and Windows), all inside Docker
├── docker-compose.yml   Postgres 16.15 + eval container; Dockerfile, requirements.txt: pinned image and packages
├── .env.example         names of the environment variables (no values)
├── config/              model sets: models.free.yaml (used), models.yaml (paid, never run)
├── lastseat/            scheduler, db API, sandbox, grader, validator, runners, report, packaging check
│   └── prompts/         contract.md: the shared prompt every model sees first
├── tasks/t01…t10/       task.md (prompt), setup.sql, spec.yaml, reference.py, wrong/, NOTES.md
├── tests/               pytest suite for the scheduler, grader, runner, report and packaging
├── results/             validation verdicts, every pilot and final run (answers, verdicts, traces)
└── docs/AI_USE.md       what Claude drafted and what the human reviewed, per milestone
```
