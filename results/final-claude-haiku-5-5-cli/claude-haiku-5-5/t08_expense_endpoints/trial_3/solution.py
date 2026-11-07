from psycopg import errors as pg_errors

_MAX_ATTEMPTS = 5
_RETRYABLE = (
    pg_errors.SerializationFailure,
    pg_errors.DeadlockDetected,
    pg_errors.LockNotAvailable,
)


def _department_of(db, expense_id):
    # department_id never changes, so an unlocked read is safe here.
    rows = db.execute(
        "SELECT department_id FROM expenses WHERE id = %s",
        (expense_id,),
    )
    return rows[0][0] if rows else None


def _approved_total(db, dept_id):
    rows = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses "
        "WHERE department_id = %s AND status = 'approved'",
        (dept_id,),
    )
    return int(rows[0][0])


def _run_locked(db, dept_id, body):
    """Run body(budget) in one transaction that holds the department row lock.

    Every operation that can change a department's approved total or budget
    takes this lock first. Such operations therefore run one at a time per
    department, and each one, under read committed, sees the committed effects
    of all earlier ones. Each transaction locks only one row, so deadlocks
    between departments cannot occur.
    """
    for attempt in range(_MAX_ATTEMPTS):
        db.begin("read committed")
        try:
            rows = db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,),
            )
            if not rows:
                db.rollback()
                return False
            result = body(rows[0][0])
            db.commit()
            return result
        except _RETRYABLE:
            db.rollback()
            if attempt == _MAX_ATTEMPTS - 1:
                raise
        except Exception:
            db.rollback()
            raise
    return False


def approve_expense(db, expense_id: int) -> bool:
    dept_id = _department_of(db, expense_id)
    if dept_id is None:
        return False

    def body(budget):
        rows = db.execute(
            "SELECT status, amount FROM expenses WHERE id = %s",
            (expense_id,),
        )
        if not rows:
            return False
        status, amount = rows[0]
        if status != "pending":
            return False
        if _approved_total(db, dept_id) + amount > budget:
            return False
        db.execute(
            "UPDATE expenses SET status = 'approved' WHERE id = %s",
            (expense_id,),
        )
        return True

    return _run_locked(db, dept_id, body)


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    dept_id = _department_of(db, expense_id)
    if dept_id is None:
        return False

    def body(budget):
        rows = db.execute(
            "SELECT status, amount FROM expenses WHERE id = %s",
            (expense_id,),
        )
        if not rows:
            return False
        status, old_amount = rows[0]
        if status == "approved":
            # The approved total includes this expense at old_amount.
            total = _approved_total(db, dept_id)
            if total - old_amount + new_amount > budget:
                return False
        db.execute(
            "UPDATE expenses SET amount = %s WHERE id = %s",
            (new_amount, expense_id),
        )
        return True

    return _run_locked(db, dept_id, body)


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    def body(_current_budget):
        if _approved_total(db, dept_id) > new_budget:
            return False
        db.execute(
            "UPDATE departments SET budget = %s WHERE id = %s",
            (new_budget, dept_id),
        )
        return True

    return _run_locked(db, dept_id, body)
