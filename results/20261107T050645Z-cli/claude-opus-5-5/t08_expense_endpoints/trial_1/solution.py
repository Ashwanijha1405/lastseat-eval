import psycopg.errors

_RETRYABLE = (
    psycopg.errors.SerializationFailure,
    psycopg.errors.DeadlockDetected,
    psycopg.errors.LockNotAvailable,
)
_MAX_ATTEMPTS = 6


def _run(db, body):
    last_exc = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            db.begin("read committed")
            result = body()
            db.commit()
            return result
        except _RETRYABLE as e:
            last_exc = e
            try:
                db.rollback()
            except Exception:
                pass
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
    raise last_exc


def _lock_dept(db, dept_id):
    rows = db.execute(
        "SELECT budget FROM departments WHERE id = %s FOR UPDATE", (dept_id,)
    )
    return rows[0][0]


def _approved_total_excluding(db, dept_id, expense_id):
    rows = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses "
        "WHERE department_id = %s AND status = 'approved' AND id <> %s",
        (dept_id, expense_id),
    )
    return int(rows[0][0])


def _dept_of_expense(db, expense_id):
    rows = db.execute(
        "SELECT department_id FROM expenses WHERE id = %s", (expense_id,)
    )
    return rows[0][0]


def approve_expense(db, expense_id: int) -> bool:
    dept_id = _dept_of_expense(db, expense_id)

    def body():
        budget = _lock_dept(db, dept_id)
        rows = db.execute(
            "SELECT amount, status FROM expenses WHERE id = %s FOR UPDATE",
            (expense_id,),
        )
        amount, status = rows[0]
        if status != "pending":
            return False
        others = _approved_total_excluding(db, dept_id, expense_id)
        if others + amount > budget:
            return False
        db.execute(
            "UPDATE expenses SET status = 'approved' WHERE id = %s", (expense_id,)
        )
        return True

    return _run(db, body)


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    dept_id = _dept_of_expense(db, expense_id)

    def body():
        budget = _lock_dept(db, dept_id)
        rows = db.execute(
            "SELECT status FROM expenses WHERE id = %s FOR UPDATE", (expense_id,)
        )
        status = rows[0][0]
        if status == "approved":
            others = _approved_total_excluding(db, dept_id, expense_id)
            if others + new_amount > budget:
                return False
        db.execute(
            "UPDATE expenses SET amount = %s WHERE id = %s", (new_amount, expense_id)
        )
        return True

    return _run(db, body)


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    def body():
        _lock_dept(db, dept_id)
        rows = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses "
            "WHERE department_id = %s AND status = 'approved'",
            (dept_id,),
        )
        total = int(rows[0][0])
        if total > new_budget:
            return False
        db.execute(
            "UPDATE departments SET budget = %s WHERE id = %s", (new_budget, dept_id)
        )
        return True

    return _run(db, body)
