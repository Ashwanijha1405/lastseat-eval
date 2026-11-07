import psycopg.errors as errors

_RETRYABLE = (errors.SerializationFailure, errors.DeadlockDetected)
_MAX_ATTEMPTS = 6


def _run(db, fn):
    last_exc = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            db.begin("read committed")
            result = fn()
            if result:
                db.commit()
            else:
                db.rollback()
            return result
        except _RETRYABLE as e:
            last_exc = e
            try:
                db.rollback()
            except Exception:
                pass
    raise last_exc


def _dept_of_expense(db, expense_id):
    # department_id never changes, so an unlocked read is safe.
    rows = db.execute(
        "SELECT department_id FROM expenses WHERE id = %s", (expense_id,)
    )
    return rows[0][0]


def _lock_dept_budget(db, dept_id):
    rows = db.execute(
        "SELECT budget FROM departments WHERE id = %s FOR UPDATE", (dept_id,)
    )
    return rows[0][0]


def _approved_total(db, dept_id):
    rows = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses "
        "WHERE department_id = %s AND status = 'approved'",
        (dept_id,),
    )
    return int(rows[0][0])


def approve_expense(db, expense_id: int) -> bool:
    dept_id = _dept_of_expense(db, expense_id)

    def body():
        budget = _lock_dept_budget(db, dept_id)
        rows = db.execute(
            "SELECT status, amount FROM expenses WHERE id = %s FOR UPDATE",
            (expense_id,),
        )
        status, amount = rows[0]
        if status != "pending":
            return False
        total = _approved_total(db, dept_id)
        if total + amount > budget:
            return False
        db.execute(
            "UPDATE expenses SET status = 'approved' WHERE id = %s",
            (expense_id,),
        )
        return True

    return _run(db, body)


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    dept_id = _dept_of_expense(db, expense_id)

    def body():
        budget = _lock_dept_budget(db, dept_id)
        rows = db.execute(
            "SELECT status, amount FROM expenses WHERE id = %s FOR UPDATE",
            (expense_id,),
        )
        status, old_amount = rows[0]
        if status == "approved":
            total = _approved_total(db, dept_id)
            if total - old_amount + new_amount > budget:
                return False
        db.execute(
            "UPDATE expenses SET amount = %s WHERE id = %s",
            (new_amount, expense_id),
        )
        return True

    return _run(db, body)


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    def body():
        _lock_dept_budget(db, dept_id)
        total = _approved_total(db, dept_id)
        if total > new_budget:
            return False
        db.execute(
            "UPDATE departments SET budget = %s WHERE id = %s",
            (new_budget, dept_id),
        )
        return True

    return _run(db, body)
