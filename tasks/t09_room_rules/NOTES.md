# t09 room rules: notes (internal, not shown to models)

**Role:** two rules on the same rows, one of which a constraint can enforce and
one it cannot. The overlap rule is t04's: an exclusion constraint handles it
completely. The 3-per-day rule is a *count*, a phantom problem: the conflicting
write is a new or moved row that did not exist (on that day) when the other
request counted, so row locks on existing rows cannot stop it. The trap is
that the constraint makes the overlap scenarios safe and looks like a full
answer. `migrate()` is allowed (an exclusion constraint is a legitimate part of
a good answer); the schema rule from t08 does not apply.

Multi-entrypoint (`book`, `reschedule`, `cancel`), using t04's schema.

## Why the reference is safe

Both rules are per (room, UTC day): bookings never cross midnight UTC, so
bookings on different days cannot overlap. The only writes that can break a
rule on day D add a booking to D (`book` on D, `reschedule` to D). Each takes
`pg_advisory_xact_lock(room_id, D - 2000-01-01)` and then checks both rules in a
new statement (READ COMMITTED: it sees everything the previous lock holder
committed). An advisory lock is a lock on a number, so it exists even when D has
no bookings yet, which is exactly what the phantom needs. Moving out of a day
and cancelling only remove bookings from a day, so they take no lock. One lock
per request: no deadlock.

The one leftover race: a `cancel` commits between reschedule's first read and
its UPDATE. The UPDATE then matches 0 rows and reschedule returns False with no
change, which is correct (the booking no longer exists).

## Scenarios

| scenario | requests | hazard |
|---|---|---|
| two bookings for the last place of a day | book / book, day has 2 | count read before the other's insert |
| two overlapping bookings of a free slot | book / book | overlap (t04) |
| a move from another day and a booking, for the last place | reschedule D1->D2 / book D2 | count, mixed functions |
| two moves from different days, for the last place | reschedule D1->D2 / reschedule D3->D2 | count, two updates |
| a move and a booking onto the same slot | reschedule D1->D2 / book D2 | overlap, mixed functions |
| two moves between two days in opposite directions | must_all_succeed | lock-order deadlock |
| a cancellation and a booking on the same day | must_all_succeed | |
| a move within a day and a booking on that day | must_all_succeed | |

## What Postgres does here (validation, all exhaustive)

- **Reference:** safe and live in every schedule (21 to 924 per scenario).
- **w1 exclusion constraint only:** overlaps never happen (the constraint waits
  on the other's uncommitted row); the count breaks in all three last-place
  scenarios. The intended trap.
- **w2 single-statement checks:** both rules break; neither statement waits.
- **w3 reschedule locks old day then new day:** safe, but two opposite moves
  deadlock (DeadlockDetected, not retried). Liveness only.
- **w4 lock the day's rows, count them:** FOR UPDATE waits, but EvalPlanQual
  re-checks only rows the statement already found, so the other's new booking
  is never counted (safety). It also deadlocks in two "both fit" scenarios,
  found by validation, not designed in (liveness).
