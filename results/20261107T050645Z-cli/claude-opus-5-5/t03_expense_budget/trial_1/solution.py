import psycopg.errors as errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS expenses_dept_status_idx "
        "ON expenses (department_id, status) INCLUDE (amount)"
    )


def _attempt(db, expense_id: int) -> bool:
    db.begin("read committed")
    try:
        rows = db.execute(
            "SELECT department_id FROM expenses WHERE id = %s", (expense_id,)
        )
        if not rows:
            db.rollback()
            return False
        dept_id = rows[0][0]

        # Serialize all approvals for this department.
        drows = db.execute(
            "SELECT budget FROM departments WHERE id = %s FOR NO KEY UPDATE",
            (dept_id,),
        )
        if not drows:
            db.rollback()
            return False
        budget = drows[0][0]

        erows = db.execute(
            "SELECT status, amount FROM expenses WHERE id = %s FOR UPDATE",
            (expense_id,),
        )
        if not erows or erows[0][0] != "pending":
            db.rollback()
            return False
        amount = erows[0][1]

        srows = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses "
            "WHERE department_id = %s AND status = 'approved'",
            (dept_id,),
        )
        total = int(srows[0][0])

        if total + amount > budget:
            db.rollback()
            return False

        db.execute(
            "UPDATE expenses SET status = 'approved' "
            "WHERE id = %s AND status = 'pending'",
            (expense_id,),
        )
        db.commit()
        return True
    except BaseException:
        try:
            db.rollback()
        except Exception:
            pass
        raise


def approve_expense(db, expense_id: int) -> bool:
    last_exc = None
    for _ in range(7):
        try:
            return _attempt(db, expense_id)
        except (
            errors.SerializationFailure,
            errors.DeadlockDetected,
            errors.LockNotAvailable,
        ) as e:
            last_exc = e
            continue
    raise last_exc
