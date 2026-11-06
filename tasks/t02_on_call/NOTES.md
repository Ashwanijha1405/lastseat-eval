# t02 on-call rota: notes (internal, not shown to models)

**Role:** textbook write skew (Kleppmann, DDIA ch. 7, doctors on call). Many
models will have seen this exact example, so a pass here mostly measures
recall. t03 is its non-textbook twin.

## What Postgres does here

- **Plain count, then update (w1).** Each request reads both rows but writes
  only its own. Writes to different rows never conflict, so neither request
  waits; both commit and the shift has nobody on call.
- **REPEATABLE READ (w2).** Snapshot isolation only rejects concurrent writes
  to the *same* row ("could not serialize access due to concurrent update").
  Both snapshots count 2 and the writes touch different rows, so both commit.
- **Locking only your own row (w4).** `FOR UPDATE` on the row you write does
  nothing about the row you read.
- **SERIALIZABLE without retry (w3).** SSI tracks what each transaction read
  (SIREAD predicate locks). R1 read Bob's row, which R2 writes, and vice
  versa: a dependency cycle, so one transaction gets 40001, at the write or
  at commit depending on the order (both are in the counterexamples). On this
  tiny table the read is a sequential scan, so the predicate lock covers the
  whole relation; requests for *different shifts* also conflict
  (counterexample 3). Safe, but valid requests fail unless retried.
- **Reference.** `SELECT id … WHERE shift_id = … AND on_call FOR UPDATE`
  locks every on-call row of the shift. The second request waits on the
  first locked row; after the first commits, READ COMMITTED re-reads the newest
  version of each waited-for row and re-checks `on_call`, so the departed
  colleague drops out. Same lock order for everyone, so no deadlock. An
  equally valid reference: SERIALIZABLE plus a bounded retry on 40001.

## Expected model failure modes

w1/w2/w4 above; SERIALIZABLE with no retry, or with a retry that does not
roll back first; counting doctors across all shifts (solo check 3).

## Validation (make validate, 2026-11-06)

| solution | fails | schedules per scenario (unsafe / unlive) |
|---|---|---|
| reference | nothing | 24, 24, 70 |
| w1_check_then_update | safety | 70 (60 unsafe), 70, 70 |
| w2_repeatable_read_conditional_update | safety | 20 (12 unsafe), 20, 20 |
| w3_serializable_no_retry | liveness | 70, 70 (60 unlive), 70 (60 unlive) |
| w4_lock_own_row_only | safety | 252 (210 unsafe), 252, 252 |

## Change log

- 2026-11-06: created. Added scenario "one leaves from each of two shifts"
  so SERIALIZABLE-without-retry also fails where the requests do not even
  touch the same shift.
