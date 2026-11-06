# t05 wallet transfer: notes (internal, not shown to models)

**Role:** core deadlock task. Safety is the easy part (t01 patterns); the
trap is liveness: opposite transfers lock the same two rows in opposite
orders. Correct fixes: a global lock order (reference), or a bounded retry
on 40P01 and 40001 with rollback.

## What Postgres does here

- **Deadlock (w1, w3, w2, w4).** A->B locks row 1 then waits for row 2;
  B->A holds row 2 and waits for row 1. After `deadlock_timeout` (50 ms) the
  waiting backend finds the cycle and aborts itself with `40P01`; the victim
  is the transaction whose wait started first (R1 in w1/w4 counterexample 1,
  R2 in w3 counterexample 3 where R2 waited first). The survivor commits.
  Data stays consistent; the victim's user sees an error.
- **SERIALIZABLE does not turn deadlocks into 40001 (w4).** Row-lock waits
  between two UPDATEs are an ordinary lock deadlock, reported as 40P01 at
  every isolation level. Retrying only `SerializationFailure` misses it.
- **Absolute writes (w2).** Lost update. In "both fit" two debits from Alice
  collapse into one, creating money. In "opposite" each request writes both
  balances, so one request's change to the shared account can be
  overwritten (42 unsafe schedules).
- **Plain check + relative update (w3).** Conserves money, overdraws Alice
  (-30) when two 40-unit transfers both pass a stale check of 50.
- **Reference.** `SELECT … WHERE id IN (a, b) ORDER BY id FOR UPDATE` locks in
  id order (LockRows runs above the Sort) and returns the newest balances.
- **Alternative reference, argument-order conditional updates + retry on
  40P01/40001:** graded ad hoc, passes (24 / 66 / 24, exhaustive).

## Scoring note

A lost transfer counts against both safety (money not conserved) and
liveness (`success_sql` "both transfers applied" fails): a request returned
True but its effect did not survive.

## Validation (make validate --task t05, 2026-11-06)

| solution | fails | schedules per scenario (unsafe / unlive) |
|---|---|---|
| reference | nothing | 36, 36, 36 |
| w1_argument_order_no_retry | liveness | 24, 30 (12 unlive), 24 |
| w2_read_then_write_balances | safety, liveness | 350 (336), 420 (42 / 406), 350 (336 / 336) |
| w3_check_then_relative_update | safety, liveness | 92 (80), 112 (40 unlive), 92 |
| w4_serializable_retry_40001_only | liveness | 92, 112 (40 unlive), 92 |

## Change log

- 2026-11-06: created.
