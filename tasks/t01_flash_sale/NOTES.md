# t01 flash sale: notes (internal, not shown to models)

**Role:** control task. The hazard is the lost update, the most widely taught
concurrency bug. Frontier models are expected to pass; if they don't, the
harder tasks are not informative either.

## What Postgres does here

- **Conditional UPDATE (reference).** `UPDATE … SET stock = stock - q WHERE id = 1 AND stock >= q`
  takes a row lock. A concurrent UPDATE of the same row waits. Under READ
  COMMITTED, when the lock holder commits, the waiter re-reads the newest
  committed version of the row and re-evaluates the WHERE clause
  (EvalPlanQual). The check and the decrement act on the same, current value.
- **Same UPDATE under REPEATABLE READ (w2).** The snapshot is fixed at the
  transaction's first statement. When the row was changed by a transaction
  that committed after that snapshot, Postgres cannot re-check against the new
  version and raises `40001 could not serialize access due to concurrent
  update`. Safe, but a valid buyer gets an error unless the code retries.
- **Plain SELECT, then write (w1, w3).** A plain SELECT takes no row lock, so
  both buyers can read the same stock. Writing an absolute value loses the
  other write (w1: conservation breaks). Writing `stock - q` keeps both
  decrements but the earlier check was stale (w3: stock goes negative).
- **`FOR UPDATE NOWAIT` (w4).** Errors with `55P03` instead of waiting, so
  refusing on that error refuses valid purchases.

## Expected model failure modes

Read-modify-write in Python (w1); check-then-act (w3); a stricter isolation
level without a retry loop (w2); refusing on lock contention (w4). A subtler
one the harness also catches: a single autocommit statement whose value comes
from a subquery, e.g. `SET stock = (SELECT stock …) - q`. The subquery is not
re-evaluated when the row lock is released (see `tests/test_scheduler.py`).

## Validation (make validate, 2026-11-06)

| solution | fails | schedules per scenario |
|---|---|---|
| reference | nothing | 24, 24 (exhaustive) |
| w1_read_then_write | safety | 92, 92 |
| w2_repeatable_read_no_retry | liveness | 24, 24 |
| w3_check_then_decrement | safety | 92, 92 |
| w4_nowait_refuses | liveness | 80, 80 |

## Change log

- 2026-11-06: created. "stock is conserved" is a per-scenario invariant
  because the starting stock differs between scenarios (the SPEC §6 example
  hard-codes 5, which would wrongly fail the 6-stock scenario).
