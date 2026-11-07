# t10 room rules, scaled: notes (internal, not shown to models)

**Role:** t09's twin. Same schema, functions, rules, reference, wrong
variants and scenarios. task.md adds one requirement (the human's wording):
"This service handles heavy traffic. Requests that affect different rooms, or
different days of the same room, must never wait for each other, even when
they arrive at the same moment."

**Why:** on t09, Nemotron (1 trial) and Opus 5.5 via `claude -p` (3 trials)
all passed by locking the whole room (`rooms` row FOR UPDATE / FOR NO KEY
UPDATE). That is safe and live but serializes requests that can never
conflict (the rules are per room *and day*). t09 cannot tell it apart from the
reference; t10 can, with `must_not_block` scenarios (SPEC §6.1).

## New scenarios (must_all_succeed and must_not_block)

| scenario | requests | why independent |
|---|---|---|
| same room, different days | book D1 / book D2, room 1 | rules are per day |
| different rooms, same day | book room 1 / book room 2, D1 | rules are per room |
| move into one day, book another | reschedule id 1 D3 -> D2 / book D1 | D3/D2 vs D1 (moving out of D3 never breaks a rule) |
| cancel on one day, book another | cancel id 1 (D1) / book D2 | cancelling only frees a place |

The moved booking starts on D3 (not D1) so the two requests share no day at all.

## What Postgres does here (validation, all exhaustive)

- **Reference** (advisory lock per room-day): 0 waits in every must_not_block
  scenario. `pg_advisory_xact_lock(room, day)` keys differ; INSERTs take only
  FOR KEY SHARE on the rooms row (foreign key), which never conflicts with
  another KEY SHARE; the UPDATE does not change room_id, so no foreign-key lock.
- **w1-w4** (t09's): unchanged results; none of them waits in the new
  scenarios (w1/w2 take no locks; w3 locks D3 then D2; w4 locks day rows).
- **w5 whole-room lock** (Nemotron's and Opus's t09 strategy): safe, live in
  all 8 t09 scenarios; blocked in the 3 same-room must_not_block scenarios
  (24/36, 46/74, 40/67 schedules); different rooms lock different rows and do
  not wait. `EXPECT: blocking`.
- **alternatives/serializable_retry.py** (SERIALIZABLE, no explicit locks,
  up to 8 tries on 40001/40P01): **passes** (1.00). It never waits, but it
  retries a lot: a 40001 in 18/35 to 240/252 schedules per scenario, including
  bookings for *different rooms* (60/70). SSI predicate locks on this tiny
  table are page/relation-level, so unrelated requests look like rw-conflicts.
  "Never wait" is not "never conflict": the rule as written accepts it.
  Not a reference and not validated (it is in `alternatives/`, not `wrong/`).
