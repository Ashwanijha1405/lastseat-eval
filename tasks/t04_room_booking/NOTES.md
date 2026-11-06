# t04 room booking: notes (internal, not shown to models)

**Role:** core phantom task. The conflicting row does not exist yet (it is the
other request's future INSERT), so there is no row to lock. Correct fixes
either let an index-backed constraint referee the write (exclusion
constraint) or lock a row that does exist (the room: materializing the
conflict, as in t03).

## What Postgres does here

- **Check, then insert (w1); REPEATABLE READ (w4).** Both checks see a free
  room. Inserts of new, different rows never conflict, under any snapshot
  isolation level.
- **`INSERT … WHERE NOT EXISTS` (w2).** The subquery reads the statement's
  snapshot, which cannot see the other request's uncommitted row; nothing
  waits. Found even though each request is a single autocommit statement,
  because the implicit COMMIT is a separate step (M1 design decision 2).
- **`FOR UPDATE` on the overlap query (w3).** An empty result locks nothing.
- **Exclusion constraint (reference).** Checked through the GiST index, which
  sees uncommitted rows of other transactions. An overlapping INSERT waits
  for the first transaction (visible in w5's counterexample 2: R1 is
  "blocked (waiting for R2)" on an INSERT), then gets 23P01 if it committed.
  Needs `btree_gist` for `room_id WITH =`; the grading role is not a superuser
  but can create it (trusted extension, database owner).
- **Closed range `'[]'` (w5).** Back-to-back bookings share the end instant
  and are refused: never unsafe, but fails the solo back-to-back check and the
  back-to-back liveness scenario.
- **Alternative reference, `rooms` row `FOR UPDATE` then check + insert:**
  graded ad hoc, passes (36 / 36 / 252 schedules, exhaustive).

## Expected model failure modes

w1–w4; closed or inclusive interval comparisons (`<=`), which the
back-to-back solo check and scenario catch; exclusion constraint without
catching `ExclusionViolation` (refusal raises instead of returning False,
caught by the solo refusal checks).

## Validation (make validate, 2026-11-06)

| solution | fails | schedules per scenario (unsafe / unlive) |
|---|---|---|
| reference | nothing | 14, 20, 20 |
| w1_check_then_insert | safety | 70 (60), 70, 70 |
| w2_insert_where_not_exists | safety | 6 (4), 6, 6 |
| w3_for_update_on_empty_result | safety | 70 (60), 70, 70 |
| w4_repeatable_read_check_then_insert | safety | 70 (60), 70, 70 |
| w5_closed_range_constraint | solo, liveness | 14, 14 (14 unlive), 20 |

## Change log

- 2026-11-06: created. First validation marked w5 *unsafe* because the
  back-to-back scenario's "both bookings exist" check was a safety
  invariant. Human decision: such checks moved to a new `success_sql`
  (counts toward liveness); the same change applied to t02 and t03.
