def approve_expense(db, expense_id: int) -> bool:
    db.begin()  # read committed; the department row lock serialises approvals
    try:
        rows = db.execute(
            "SELECT department_id FROM expenses WHERE id = %s",
            (expense_id,),
        )
        if not rows:
            db.rollback()
            return False
        department_id = rows[0][0]

        # Serialise every approval for this department. Later lockers wait
        # here until the earlier transaction commits, so they then see its
        # approved rows in their statement snapshots.
        locked = db.execute(
            "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
            (department_id,),
        )
        if not locked:
            db.rollback()
            return False
        budget = locked[0][0]

        # Read the expense after taking the lock.
        rows = db.execute(
            "SELECT amount, status FROM expenses WHERE id = %s",
            (expense_id,),
        )
        if not rows:
            db.rollback()
            return False
        amount, status = rows[0]
        if status != "pending":
            db.rollback()
            return False

        approved_total = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses "
            "WHERE department_id = %s AND status = 'approved'",
            (department_id,),
        )[0][0]
        if approved_total + amount > budget:
            db.rollback()
            return False

        updated = db.execute(
            "UPDATE expenses SET status = 'approved' "
            "WHERE id = %s AND status = 'pending' RETURNING id",
            (expense_id,),
        )
        if not updated:
            db.rollback()
            return False

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
