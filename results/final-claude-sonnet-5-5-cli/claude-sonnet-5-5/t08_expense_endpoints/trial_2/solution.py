import psycopg.errors


def _dept_of_expense(db, expense_id):
    rows = db.execute(
        "SELECT department_id FROM expenses WHERE id = %s", (expense_id,)
    )
    return rows[0][0] if rows else None


def _lock_dept(db, dept_id):
    rows = db.execute(
        "SELECT budget FROM departments WHERE id = %s FOR NO KEY UPDATE",
        (dept_id,),
    )
    return rows[0][0] if rows else None


def _approved_total(db, dept_id):
    rows = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses "
        "WHERE department_id = %s AND status = 'approved'",
        (dept_id,),
    )
    return int(rows[0][0])


def approve_expense(db, expense_id: int) -> bool:
    db.begin("read committed")
    try:
        rows = db.execute(
            "SELECT department_id FROM expenses WHERE id = %s", (expense_id,)
        )
        if not rows:
            db.rollback()
            return False
        dept_id = rows[0][0]
        budget = _lock_dept(db, dept_id)
        rows = db.execute(
            "SELECT status, amount FROM expenses WHERE id = %s", (expense_id,)
        )
        if not rows or rows[0][0] != "pending":
            db.rollback()
            return False
        amount = rows[0][1]
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
    db.begin("read committed")
    try:
        rows = db.execute(
            "SELECT department_id FROM expenses WHERE id = %s", (expense_id,)
        )
        if not rows:
            db.rollback()
            return False
        dept_id = rows[0][0]
        budget = _lock_dept(db, dept_id)
        rows = db.execute(
            "SELECT status, amount FROM expenses WHERE id = %s", (expense_id,)
        )
        if not rows:
            db.rollback()
            return False
        status, old_amount = rows[0]
        if status == "approved":
            total = _approved_total(db, dept_id)
            if total - old_amount + new_amount > budget:
                db.rollback()
                return False
        db.execute(
            "UPDATE expenses SET amount = %s WHERE id = %s",
            (new_amount, expense_id),
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
        budget = _lock_dept(db, dept_id)
        if budget is None:
            db.rollback()
            return False
        total = _approved_total(db, dept_id)
        if total > new_budget:
            db.rollback()
            return False
        db.execute(
            "UPDATE departments SET budget = %s WHERE id = %s",
            (new_budget, dept_id),
        )
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
