def approve_expense(db, expense_id: int) -> bool:
    db.begin("read committed")
    try:
        # department_id never changes, so it is safe to read before locking.
        rows = db.execute(
            "SELECT department_id FROM expenses WHERE id = %s", (expense_id,)
        )
        if not rows:
            db.rollback()
            return False
        dept_id = rows[0][0]

        # Serialize all approvals for this department by locking its row.
        # Every request takes only this one lock first, so there are no deadlocks.
        drows = db.execute(
            "SELECT budget FROM departments WHERE id = %s FOR UPDATE", (dept_id,)
        )
        budget = drows[0][0]

        # In READ COMMITTED each statement gets a fresh snapshot, so after
        # acquiring the lock we see all approvals committed by earlier holders.
        erows = db.execute(
            "SELECT status, amount FROM expenses WHERE id = %s", (expense_id,)
        )
        status, amount = erows[0]
        if status != "pending":
            db.rollback()
            return False

        srows = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses "
            "WHERE department_id = %s AND status = 'approved'",
            (dept_id,),
        )
        approved_total = int(srows[0][0])

        if approved_total + amount > budget:
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
