import psycopg.errors

_RETRYABLE = (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected)
_MAX_ATTEMPTS = 5


def _approve_locked(db, expense_id: int) -> bool:
    # Find the expense's department (department_id never changes).
    rows = db.execute("SELECT department_id FROM expenses WHERE id = %s", (expense_id,))
    if not rows:
        return False
    dept_id = rows[0][0]

    # Serialise all approvals for this department. The department row is always
    # locked before any expense row, so lock ordering is consistent across requests.
    # FOR NO KEY UPDATE does not conflict with the FK share locks taken by
    # unrelated inserts into expenses.
    budget_rows = db.execute(
        "SELECT budget FROM departments WHERE id = %s FOR NO KEY UPDATE", (dept_id,)
    )
    if not budget_rows:
        return False
    budget = budget_rows[0][0]

    # Lock this expense and re-read its status now that we hold the department lock.
    exp_rows = db.execute(
        "SELECT status, amount FROM expenses WHERE id = %s FOR UPDATE", (expense_id,)
    )
    if not exp_rows:
        return False
    status, amount = exp_rows[0]
    if status != "pending":
        return False

    # This statement starts after the department lock is held, so under read
    # committed it sees every approval committed before us.
    total = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses "
        "WHERE department_id = %s AND status = 'approved'",
        (dept_id,),
    )[0][0]
    if total + amount > budget:
        return False

    db.execute(
        "UPDATE expenses SET status = 'approved' WHERE id = %s AND status = 'pending'",
        (expense_id,),
    )
    return True


def _attempt(db, expense_id: int) -> bool:
    db.begin()  # read committed
    try:
        ok = _approve_locked(db, expense_id)
    except BaseException:
        db.rollback()
        raise
    if ok:
        db.commit()
    else:
        db.rollback()  # nothing was changed
    return ok


def approve_expense(db, expense_id: int) -> bool:
    last_error = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            return _attempt(db, expense_id)
        except _RETRYABLE as exc:
            last_error = exc  # rolled back inside _attempt; retry immediately
    raise last_error
