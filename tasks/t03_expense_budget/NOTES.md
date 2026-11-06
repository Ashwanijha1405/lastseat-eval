# t03 expense budget: notes (internal, not shown to models)

**Role:** non-textbook twin of t02. Same hazard class (write skew), but the
t02 fix, "lock the rows you read", does not work: the row that breaks the
budget is *pending* when the other request reads, so it is never in the set
being locked. The fix is to lock a row every approval must touch (the
department), i.e. materialize the conflict, or use SERIALIZABLE with retry.

## What Postgres does here

- **Plain sum, then update (w1).** Both sums run before either approval
  commits; the two UPDATEs touch different expense rows, so nobody waits.
- **FOR UPDATE on approved rows, sum in Python (w2).** With nothing approved
  the query locks zero rows. With one approved row both requests lock it and
  take turns, but when R2 resumes, Postgres re-checks only the rows R2 waited
  on (EvalPlanQual); R1's newly approved row was not in R2's scan result, so
  R2 still returns `[(30,)]` (counterexample 2).
- **Department lock under REPEATABLE READ (w3).** The snapshot is taken at the
  first statement, the blocking `FOR UPDATE`, so it predates R1's commit. R1
  only locked the department row (did not update it), so no 40001 is raised;
  R2's later SUM still sees 0 / 30.
- **FOR UPDATE on approved rows, then a fresh SUM (w4).** Accidentally safe
  when an approved row exists (both lock it, and the later READ COMMITTED
  statement sees R1's commit); unsafe when none exists. The "nothing
  approved yet" scenario is what catches it.
- **Reference.** Lock the department row, then read status/amount/sum in a
  new statement. READ COMMITTED gives that statement a fresh snapshot after
  the lock is granted. Approvals in different departments do not wait.

## Expected model failure modes

w2 is the most likely: models that learned "lock what you read" from the
textbook doctors example apply it here. w3 for models that reach for
REPEATABLE READ "to be safe". SERIALIZABLE without retry (cf. t02 w3).

## Validation (make validate, 2026-11-06)

| solution | fails | schedules per scenario (unsafe) |
|---|---|---|
| reference | nothing | 36, 36, 36, 252 (all exhaustive) |
| w1_check_then_update | safety | 924 (756), 924 (756), 924, 924 |
| w2_lock_approved_rows_sum_in_python | safety | 924 (756), 350 (182), 350, 924 |
| w3_department_lock_repeatable_read | safety | 50 (36), 50 (36), 50, 924 |
| w4_lock_approved_rows_then_sum | safety | 924 (756), 148 (0), 148, 924 |

## Change log

- 2026-11-06: created. First reference used 7 steps per request; the
  two-department scenario hit the 2000-schedule cap (C(14,7) = 3432), so it
  was rewritten to 5 steps (same lock-then-read logic) to explore exhaustively.
