# t07 node drain: notes (internal, not shown to models)

**Role:** stretch. Combines t02/t03 (write skew across a group, fixed by
locking a row every participant must lock) with t05 (lock order): one drain
touches several groups, so a correct per-group lock taken in an inconsistent
order deadlocks.

## What Postgres does here

- **Plain check, then update (w1).** Write skew on the shared shard: both
  checks pass, the updates touch different rows, shard 1 ends with no active
  replica.
- **Deactivate first, then verify with FOR UPDATE (w2).** Each drain holds its
  own updated rows and then wants the other's: deadlock, 40P01.
- **Per-shard locks in storage order (w3).** The seed stores node A's replicas
  as shard 1 then 2 and node B's as shard 2 then 1 (deliberate, documented
  in spec.yaml). `SELECT … WHERE node_id = …` returns them in that physical
  order (sequential scan on a tiny table), so the two drains lock shards in
  opposite orders: deadlock. Safe, not live.
- **Sorted shard locks under REPEATABLE READ (w4).** Same as t03 w3: the
  snapshot is taken by the blocking lock statement; the other drain only
  locked shard rows, so no 40001; the check uses the stale snapshot.
- **Reference.** One `SELECT … FROM shards … ORDER BY id FOR UPDATE` locks all
  affected shards in ascending order, then a fresh READ COMMITTED check.

## Expected model failure modes

Per-shard loops without sorting (w3) are the target of this task; w1 and
w4 carry over from t02/t03.

## Validation (make validate, 2026-11-06)

| solution | fails | schedules per scenario (unsafe / unlive) |
|---|---|---|
| reference | nothing | 36, 36, 252 |
| w1_check_then_update | safety | 70 (60), 70, 70 |
| w2_deactivate_then_verify | liveness | 30, 30 (12 unlive), 70 |
| w3_per_shard_locks_unsorted | liveness | 148, 168 (40 unlive), 252 |
| w4_sorted_lock_repeatable_read | safety | 36 (24), 36, 252 |

## Change log

- 2026-11-06: created (stretch task).
