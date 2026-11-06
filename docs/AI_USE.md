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

---

## M3 / t03 expense budget (2026-11-06, Claude Code / Claude Opus 5.5)

**Drafted by Claude**
- `tasks/t03_expense_budget/`: task.md, setup.sql (departments, expenses),
  spec.yaml (5 solo checks; 4 scenarios: nothing approved / one approved,
  both "only one fits", plus same-department and cross-department "both
  fit"), reference (department row `FOR UPDATE`, then fresh read), four
  wrong variants (w1 plain sum, w2 `FOR UPDATE` approved rows + Python sum,
  w3 department lock under REPEATABLE READ, w4 `FOR UPDATE` approved rows +
  fresh SUM), NOTES.md.

**Verified by Claude**
- `make validate`: t01–t03 green; every counterexample reproduces.
- Predictions written before running, all confirmed by the harness: w3 is
  unsafe (snapshot taken by the blocking first statement, no 40001 because
  the department row was only locked); w4 is safe with an approved row
  present and unsafe with none.
- Reference first hit the 2000-schedule cap in one scenario; rewritten from
  7 to 5 steps per request so every scenario is exhaustive.

**Human to review**
- `tasks/t03_expense_budget/task.md` wording.
- Grading cost: wrong variants with ~924 schedules per scenario take
  80–150 s each. Model solutions will be similar, so M4/M6 likely needs
  parallel grading (one subprocess per solution; db names already include
  the pid).

---

## M3 / t04 room booking + `success_sql` (2026-11-06, Claude Code / Claude Opus 5.5)

**Drafted by Claude**
- `tasks/t04_room_booking/`: task.md, setup.sql (rooms, bookings), spec.yaml
  (5 solo checks incl. back-to-back and contained interval; 3 scenarios),
  reference (`migrate()` adds `btree_gist` + `EXCLUDE USING gist` on
  `'[)'` ranges; insert catches `ExclusionViolation`), five wrong variants
  (w1 check-then-insert, w2 `INSERT … WHERE NOT EXISTS`, w3 `FOR UPDATE` on
  empty result, w4 REPEATABLE READ, w5 closed `'[]'` range), NOTES.md.
- Grader change (human-approved): scenario key `success_sql` (allowed only in
  `must_all_succeed` scenarios) whose checks count toward **liveness**;
  `Invariant.kind` = safety | success; traces print `SUCCESS CHECK FAILED`.
  t02/t03 liveness-scenario checks moved to `success_sql`. Loader test added.

**Why the grader changed** (not to force a result): validation flagged w5
as failing safety, because "both bookings exist" was a safety invariant.
w5 never double-books; the check verifies rule 2 (valid requests succeed).
Human chose to reclassify such checks as liveness.

**Verified by Claude**
- `make validate` (all four tasks) green after the change; `make test` 51.
- Mutation: reference without `commit()` → safety 0.5 kept, liveness 0
  (`SUCCESS CHECK FAILED: both bookings exist`), solo 0.
- Alternative reference (lock `rooms` row) graded ad hoc: passes.

**Human to review**
- `tasks/t04_room_booking/task.md` wording; the datetime signature.
- Whether t02's "Chen is still on call" belongs in liveness (it encodes
  "only this doctor's row may change", stated under Behaviour).

---

## M3 / t05 wallet transfer (2026-11-06, Claude Code / Claude Opus 5.5)

**Drafted by Claude**
- `tasks/t05_wallet_transfer/`: task.md, setup.sql (accounts), spec.yaml
  (4 solo checks; 3 scenarios: overdraft race, opposite transfers, two
  debits that both fit, with per-scenario conservation invariants and
  `success_sql`), reference (lock both rows `ORDER BY id FOR UPDATE`), four
  wrong variants (w1 argument order no retry, w2 absolute writes, w3 stale
  check + relative updates, w4 SERIALIZABLE retrying only 40001), NOTES.md.

**Verified by Claude**
- `make validate TASK=t05_wallet_transfer` green; all failures reproduce.
  All four EXPECT lines were written as predictions before running.
- Retry-based alternative reference graded ad hoc: passes.
- Full `make validate` (all tasks) not re-run for t05; scheduled once after
  t06 so `results/validation.md` covers every task in one run.

**Human to review**
- `tasks/t05_wallet_transfer/task.md` wording (rule 3 names "opposite
  directions" as a valid concurrent case without naming the hazard).
- Scoring note: a lost transfer fails both safety and liveness.

---

## M3 / t06 idempotent payment + return-value checks (2026-11-06, Claude Code / Claude Opus 5.5)

**Drafted by Claude**
- `tasks/t06_idempotent_payment/`: task.md, setup.sql (payments, no unique
  constraint), spec.yaml (3 solo checks; 3 scenarios: same key safety-only,
  same key both must get the id, different keys), reference (`migrate()`
  adds `UNIQUE`, `ON CONFLICT DO NOTHING RETURNING id`, then a separate
  re-read), four wrong variants (w1 select-then-insert, w2 no re-read,
  w3 everything in REPEATABLE READ, w4 unhandled `UniqueViolation`), NOTES.md.
- Grader extension (needed for SPEC §7 "both return the same payment id"):
  - task key `success_means: returns_true | returns` (default
    `returns_true`, so t01–t05 are unchanged);
  - checks may bind return values as `%(r1)s`, `%(r2)s` (NULL if raised);
  - solo `expect_return` optional when `expect_sql` is present.
- Test for the new loader fields.

**Verified by Claude**
- `make validate` (all six tasks) green; `make test` 52 passed.
- w3 prediction confirmed: `40001 … due to concurrent update` at the INSERT
  under REPEATABLE READ; SERIALIZABLE checked ad hoc, same error.
- Alternative reference (catch `UniqueViolation`, re-read) passes.
- w1 EXPECT corrected from `safety` to `safety, liveness` after the harness
  showed it returns ids 1 and 2 for one key. Grader unchanged.

**Human to review**
- The grader extension above (new capability; earlier verdicts identical).
- `tasks/t06_idempotent_payment/task.md`, especially "must return the id as
  an int (never None) and must not raise".
- w1's corrected EXPECT.

---

## M3 / t07 node drain, stretch (2026-11-06, Claude Code / Claude Opus 5.5)

**Drafted by Claude**
- `tasks/t07_node_drain/`: task.md, setup.sql (nodes, shards, replicas),
  spec.yaml (3 solo checks incl. all-or-nothing refusal; 3 scenarios; the
  "both fit" seed stores rows in a deliberate order so unsorted per-shard
  locking deadlocks), reference (all affected shard rows `ORDER BY id
  FOR UPDATE`, then fresh check), four wrong variants (w1 plain check,
  w2 deactivate-then-verify, w3 per-shard locks unsorted, w4 sorted locks
  under REPEATABLE READ), NOTES.md.

**Verified by Claude**
- `make validate TASK=t07_node_drain` green; all four EXPECT lines written as
  predictions before running, all confirmed. w3 trace shows opposite shard
  orders `[1, 2]` vs `[2, 1]` and the 40P01.

**Human to review**
- Whether relying on physical row order in the seed is acceptable (it is
  deterministic: fresh template clone, no autovacuum, sequential scan).

---

## M4: model runner (2026-11-06, Claude Code / Claude Opus 5.5)

**Drafted by Claude**
- `lastseat/runner.py`:
  - `models` subcommand: live OpenRouter catalog lookup (no key) of the
    configured IDs, prices, context, supported parameters.
  - `run`: prompt = contract.md + task.md; OpenRouter chat completions via
    stdlib `urllib` (no new dependency); retries only on 429/5xx/network
    with backoff; last ```python block extracted; saves prompt.txt,
    request.json, raw_response.txt, response.json, api.json, solution.py;
    grades each solution in its own process; merges tokens/cost into
    verdict.json; `no_code` and `api_error` verdicts; resumable by run id;
    `--jobs` parallel grading; run_meta.json (git commit, models, settings
    sent, list prices, Postgres version, scheduler caps, spend).
  - Cost guard: estimate printed first (pilot token counts via
    `--estimate-from`, else 8k output tokens/call, plus worst case at
    `max_tokens`); paid run needs `--yes`; stops before any call whose worst
    case would exceed `LASTSEAT_MAX_COST_USD`.
  - Paid runs refused unless `config/models.yaml` has `confirmed: true`.
  - `--dry-run`: mock model returns each task's reference.
- `config/models.yaml` (proposed, unconfirmed), Makefile targets
  `models / dry-run / pilot / run`, `tests/test_runner.py` (11 tests, no
  network).

**Verified by Claude**
- `make test`: 63 passed. `make dry-run` (4 models × 7 tasks, 2 grading
  jobs): 28/28 references pass, $0. `make pilot` with `confirmed: false`
  refuses without touching the network. `make models`: all four proposed IDs
  exist and support `reasoning` and `max_tokens`.
- No paid API call has been made.

**Human to review / decide**
- Model IDs (exact strings from the live catalog) and whether the four
  proposed models are the right ones.
- Settings: `max_tokens: 32000`, `reasoning: {effort: high}`, no temperature.
- Budget (`LASTSEAT_MAX_COST_USD`): estimate pilot ≈ $2.6 typical / $10
  worst; full run ≈ $13 typical / $50 worst.

## M4b step 1: free model set (zero spend enforced in code)

Context: no international card, so runs default to free OpenRouter models.
The paid path stays working behind `--config paid`.

**Claude drafted**
- `config/models.free.yaml` (`tier: free`, default) next to the paid
  `config/models.yaml` (`tier: paid`); same settings in both.
- `lastseat/runner.py`: `--config free|paid|<path>` on `run` and `models`;
  `models --list-free`. Free-tier guards, each with a test:
  1. load time: every ID must end in `:free`; `provider` may not be set;
  2. start: `LASTSEAT_MAX_COST_USD` must be 0 or unset (budget is $0);
  3. start: live catalog must list every price of every model as exactly 0;
  4. every request carries `provider.max_price` = 0 (OpenRouter refuses a
     paid route);
  5. after each reply: any reported cost > 0 stops the run at once.
  A paid run now needs `LASTSEAT_MAX_COST_USD > 0`.
- `run.ps1`: PowerShell twin of the Makefile (`-Config -Yes -Run -From -Jobs
  -Task -Model`). Makefile: `CONFIG=`, `free-models`.
- 6 new tests in `tests/test_runner.py`.

**Verified by Claude**
- `make test`: 69 passed. Mutation check: disabling guard 1, 3, 4 or 5 makes
  a test fail (guard 2 is checked before any network access by its test).
- `.\run.ps1 models` / `free-models` / `pilot` work on Windows PowerShell
  5.1; the pilot refuses while `confirmed: false`. No model API call made.
- Not yet verified live: that free endpoints accept `provider.max_price` = 0
  (the docs say a request fails if no provider is within the cap). The first
  pilot request will show it.

**Human to review / decide**
- Pick 2 free models; then set `confirmed: true` in `config/models.free.yaml`.
- Interpretation: "refuse if LASTSEAT_MAX_COST_USD > 0" was implemented as a
  hard refusal for free runs.

## M4b step 2: free-tier limits, resume, 429 handling

**Claude drafted** (`lastseat/runner.py`, `config/models.free.yaml: limits`)
- `RateLimiter`: at most one request start every 4 s.
- `DailyQuota` in `results/.free_quota.json` (gitignored): every HTTP
  attempt, retries included, is counted before it is sent; resets on a new
  UTC date; synced at run start with OpenRouter's own counter
  (`GET /api/v1/key` -> `free_model_daily_requests`, only used/limit/remaining
  are kept). The 51st request of the day is never sent.
- 429: per-minute -> honour `Retry-After` or back off, up to 3 retries;
  daily (`X-RateLimit-Remaining: 0`, reset > 2 min away) -> stop at once.
- Transport errors, 429s, quota exhaustion and rejected requests (4xx) no
  longer write a verdict: the run stops, `api_error.txt` records the error,
  and the cell stays missing. (Before, a rejected request was scored as an
  `api_error` verdict and skipped on resume.)
- Resume by default: the same command continues the newest unfinished run
  with the same config/models/tasks/trials (`--new` forces a fresh run).
  `run_meta.json` keeps totals plus one entry per session.
- `api.json` now records `finish_reason` (to tell truncation from no code).
- `quota` command (`make quota`, `.\run.ps1 quota`).

**Verified by Claude**
- `make test`: 76 passed. Mutation check: removing the gate, retrying a
  daily 429, scoring a 429 as a verdict, or disabling auto-resume each fails
  a test. (The resume test first passed by accident: two runs in the same
  second got the same timestamp id. Fixed in the test.)
- `.\run.ps1 dry-run`: 14/14 pass. `.\run.ps1 quota`: OpenRouter reports
  0 of 50 used.

**Human to review**
- Policy: any 4xx stops the whole run without a verdict. A model that always
  rejects one prompt would block resume until handled by hand.
- Two runs at once would race on the quota file (not locked).

## Pilot review fixes: vacuous safety, several entrypoints per task

**Claude drafted**
- Grader (`lastseat/grade.py`): safety is 0, with `safety_reason:
  "vacuous_safety"`, unless at least one solo check that expects the
  operation to succeed passed (`Task.expects_success`: `expect_return: true`,
  or any check when `success_means: returns`). The human chose this over the
  literal "solo score 0" rule, which would also have zeroed safety for two
  genuinely safe wrong variants that fail one edge case (t04 w5, t06 w2).
  `validate.py` policy: every task needs such a solo check. SPEC §6.1 updated.
- Harness: `entrypoints: [a, b, ...]` in spec.yaml, and `{fn, args}` calls in
  solo checks and concurrent requests (`task.Call`). Single-entrypoint tasks
  keep their bare argument mappings. The sandbox loads every named function;
  a missing one is `missing_entrypoint`. Traces print `R1: fn(db, ...)`.
  SPEC §6 updated. The shared contract is unchanged (so t01-t07 prompts stay
  identical across the pilot); a multi-function task says in its task.md that
  every function must be defined and that they run concurrently.
- Tests: `tests/test_grade.py` (vacuous safety; a two-function toy task where
  each function is right alone but a deposit/withdraw race breaks safety);
  spec-format tests in `tests/test_task.py`.

**Verified by Claude**
- Without the rule, 2 vacuous-safety tests fail; with fn dispatch broken
  (always the first function), 2 multi-function tests fail.
- Pilot re-graded from disk (no API calls): only nemotron t07 changed,
  0.50 -> 0.00 (`vacuous_safety`). Previous verdicts kept as
  `verdict.prev.json`.

**Human to review**
- `grade.py`: the rule runs after the component scores, and only flips
  safety (the scheduler's per-scenario `safe` flags are untouched).
- `task.py` `_call`: a bare argument mapping is allowed only when the task
  has one entrypoint; check you agree with that restriction.
- `results/validation/`: all t01-t07 verdicts were regenerated (they now
  carry `safety_reason`); the 36 EXPECT outcomes are unchanged.

## t08 expense endpoints (2026-11-06, Claude Code / Claude Opus 5.5)

**Claude drafted**
- `tasks/t08_expense_endpoints/`: three entrypoints (`approve_expense`,
  `edit_expense`, `change_budget`) over t03's schema. Invariant: approved
  total <= budget per department. 9 solo checks (3 per function), 4 safety
  scenarios mixing functions, 3 `must_all_succeed` scenarios (two in one
  department, one across two departments).
- Reference: every function locks the department row FOR UPDATE, then reads
  status / amount / total in a new statement (READ COMMITTED). One lock per
  request, so no deadlock.
- Wrong variants (all `EXPECT: safety`): w1 unprotected edit; w2 unprotected
  change_budget; w3 edit locks the expense row instead of the department;
  w4 (Claude's addition) edit skips the lock when the expense reads pending.
- task.md does not name the hazard (grep for lock/race/concurren/skew/
  isolation found nothing beyond "run at the same time").

**Verified by Claude**
- `validate t08`: reference safe and live in every scenario, exhaustive
  (36 schedules per one-department scenario, 252 across departments).
  w1 and w3 fail 3 safety scenarios, w2 the 2 budget-cut ones, w4 only
  "a pending expense is raised while it is being approved".
- The w2 and w4 docstrings were rewritten to match the counterexample traces
  Postgres actually produced; no grader or scheduler change.

**Human to review**
- Whether "an approved expense may be raised" and "a pending expense may be
  raised above the budget" are the business rules you want.
- w4: keep it as a fourth variant, or drop it.
- The numbers in each scenario: each request must fit alone and the pair
  must not (safety scenarios), or both must fit in either order
  (`must_all_succeed`).
