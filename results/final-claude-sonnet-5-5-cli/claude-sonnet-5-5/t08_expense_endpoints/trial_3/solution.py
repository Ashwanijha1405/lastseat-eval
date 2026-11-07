import psycopg.errors


def _lock_dept(db, dept_id):
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
    rows = db.execute(
        "SELECT department_id FROM expenses WHERE id = %s", (expense_id,)
    )
    dept_id = rows[0][0]
    db.begin("read committed")
    try:
        budget = _lock_dept(db, dept_id)
        rows = db.execute(
            "SELECT status, amount FROM expenses WHERE id = %s", (expense_id,)
        )
        status, amount = rows[0]
        if status != "pending":
            db.rollback()
            return False
        total = _approved_total(db, dept_id)
        if total + amount > budget:
            db.rollback()
            return False
        db.execute(
            "UPDATE expenses SET status = 'approved' WHERE id = %s", (expense_id,)
        )
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    rows = db.execute(
        "SELECT department_id FROM expenses WHERE id = %s", (expense_id,)
    )
    dept_id = rows[0][0]
    db.begin("read committed")
    try:
        budget = _lock_dept(db, dept_id)
        rows = db.execute(
            "SELECT status, amount FROM expenses WHERE id = %s", (expense_id,)
        )
        status, amount = rows[0]
        if status == "approved":
            total = _approved_total(db, dept_id)
            if total - amount + new_amount > budget:
                db.rollback()
                return False
        db.execute(
            "UPDATE expenses SET amount = %s WHERE id = %s", (new_amount, expense_id)
        )
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    db.begin("read committed")
    try:
        _lock_dept(db, dept_id)
        total = _approved_total(db, dept_id)
        if total > new_budget:
            db.rollback()
            return False
        db.execute(
            "UPDATE departments SET budget = %s WHERE id = %s", (new_budget, dept_id)
        )
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
