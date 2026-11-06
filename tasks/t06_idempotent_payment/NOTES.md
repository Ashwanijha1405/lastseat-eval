# t06 idempotent payment: notes (internal, not shown to models)

**Role:** core / hardest. Getting safety right is one unique constraint; the
difficulty is the second half of the contract: every concurrent attempt must
*return the same id*, which requires knowing that `ON CONFLICT DO NOTHING`
returns no row and that the re-read must see the other attempt's commit.

## What Postgres does here

- **Select, then insert, no constraint (w1).** Phantom: both lookups find
  nothing, both insert. Two payments (safety) *and* two different ids
  returned for one checkout (liveness: rule 2).
- **Unique index waits on uncommitted rows.** With `UNIQUE (idempotency_key)`
  the second attempt's INSERT blocks until the first commits or rolls back
  (visible as "blocked (waiting for R1)" in w3's trace).
- **`ON CONFLICT DO NOTHING RETURNING id` (w2).** On conflict it returns
  `[]`, with no error. Without a re-read the function returns `None`, alone
  (solo check) and concurrently.
- **REPEATABLE READ / SERIALIZABLE (w3, and SERIALIZABLE checked ad hoc).** If
  the conflicting row was committed after the transaction's snapshot,
  `ON CONFLICT` raises `40001 could not serialize access due to concurrent
  update` at the INSERT: it refuses to act on a row its snapshot cannot see.
  Same result at SERIALIZABLE. A retry loop would fix this; none here.
- **Unhandled `UniqueViolation` (w4).** Safe, but the losing attempt errors.
- **Reference.** Autocommit `INSERT … ON CONFLICT DO NOTHING RETURNING id`;
  if no row, a separate autocommit `SELECT` (fresh READ COMMITTED snapshot).
- **Alternative reference, plain INSERT + catch `UniqueViolation` + re-read:**
  graded ad hoc, passes.

## Grader features this task introduced

- `success_means: returns`: success = the call returns without raising.
- Checks may bind returned values as `%(r1)s`, `%(r2)s` (NULL if a request
  raised); `expect_return` is optional when `expect_sql` checks the id.

## Expected model failure modes

w2 (forgetting that DO NOTHING returns nothing) and w3 (wrapping everything
in one REPEATABLE READ/SERIALIZABLE transaction) are the interesting ones;
w1 and w4 are the textbook mistakes.

## Validation (make validate, 2026-11-06)

| solution | fails | schedules per scenario (unsafe / unlive) |
|---|---|---|
| reference | nothing | 4, 4, 6 |
| w1_select_then_insert | safety, liveness | 70 (60), 70 (60 / 60), 70 |
| w2_on_conflict_no_reread | solo, liveness | 4, 4 (4 unlive), 6 |
| w3_reread_in_repeatable_read | liveness | 14, 14 (6 unlive), 20 |
| w4_unique_but_unhandled | liveness | 50, 50 (40 unlive), 70 |

## Change log

- 2026-11-06: created. w1's EXPECT was first written as `safety` only; the
  harness showed it also returns two different ids for one key (rule 2), so
  the EXPECT now lists `safety, liveness`. Prediction corrected, grader
  unchanged.
