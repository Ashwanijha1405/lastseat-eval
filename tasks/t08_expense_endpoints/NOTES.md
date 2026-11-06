# t08 expense endpoints: notes (internal, not shown to models)

**Role:** t03's write skew spread over three functions. The fix is the same
(every request that can change a department's approved total or budget takes
the department row lock, then reads), but now it must be applied
*consistently*: one function that checks without that lock, or locks a
different row, breaks the invariant even though each function is correct on
its own and the other two are correct too. The prompt does not name the
hazard; it only says the three functions run at the same time.

New harness feature used: `entrypoints: [...]` and `{fn, args}` requests.

**Schema fixed** (`allow_migrate: false`): task.md says schema changes go through a
separate review, so no `migrate()`, tables, columns, triggers or constraints. A
running-total column with a CHECK would turn the task into a one-row update and
skip the cross-function locking discipline it is meant to test.

## Scenarios

| scenario | requests | hazard it targets |
|---|---|---|
| approval + raise, not both fit | approve(2) / edit(1 -> 60), budget 100, 40 approved | approve and edit change the total via different rows |
| approval + budget cut, not both fit | approve(2) / change_budget(60) | total grows while the budget shrinks |
| raise + budget cut, not both fit | edit(1 -> 70) / change_budget(50) | same, with edit |
| pending expense raised while approved | approve(1) / edit(1 -> 90), budget 50 | edit of a "pending" expense that is no longer pending |
| approval + raise, both fit | must_all_succeed | serializing must not refuse valid requests |
| approval + budget cut, both fit | must_all_succeed | same |
| two departments | must_all_succeed | the lock must be per department, not global |

## What Postgres does here (validation, all exhaustive)

- **Reference:** 36 schedules per one-department scenario (the second request
  waits for the department lock), 252 when the departments differ (no
  waiting). All safe and live.
- **w1 unprotected edit:** edit reads the total with no lock and writes a
  different row than the approval, so neither waits. Fails 3 of 4 safety
  scenarios (not the budget-cut one, where edit is not involved).
- **w2 unprotected change_budget:** sums, then updates the department row;
  the sum is stale. Fails the two budget-cut scenarios only.
- **w3 edit locks the expense row:** a lock, but not the shared one. Same
  scenarios as w1.
- **w4 edit skips the lock for pending expenses:** only the
  "pending expense raised while approved" scenario catches it (counterexample:
  the status `pending` it read is stale when its UPDATE runs).

- **w5 running-total column:** defines `migrate()` (column + trigger + CHECK).
  Refused at load with `forbidden_migrate`, never graded. The design itself may
  well be safe; it exists to prove the schema rule is enforced.

## Expected model failure modes

Correct t03-style approve, then a natural-looking edit/change_budget that
"just updates one row" without the department lock (w1/w2), or a lock on the
row being changed (w3). w4 is the subtle one: skipping the lock on a path
that needs no budget check.
