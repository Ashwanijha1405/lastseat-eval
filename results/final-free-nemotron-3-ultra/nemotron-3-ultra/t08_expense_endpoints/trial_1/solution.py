import psycopg.errors

def _retry_transaction(db, func, max_attempts=5):
    """Helper to run a transaction with retries on serialization/deadlock errors."""
    for attempt in range(max_attempts):
        try:
            db.begin()
            result = func(db)
            db.commit()
            return result
        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            db.rollback()
            if attempt == max_attempts - 1:
                return False
        except Exception:
            db.rollback()
            raise
    return False

def approve_expense(db, expense_id: int) -> bool:
    def _run(db):
        # Get department_id (no lock needed, it never changes)
        rows = db.execute(
            "SELECT department_id FROM expenses WHERE id = %s",
            (expense_id,)
        )
        if not rows:
            return False
        dept_id = rows[0][0]

        # Lock department row
        db.execute(
            "SELECT * FROM departments WHERE id = %s FOR UPDATE",
            (dept_id,)
        )

        # Lock expense row
        rows = db.execute(
            "SELECT id, amount, status FROM expenses WHERE id = %s FOR UPDATE",
            (expense_id,)
        )
        if not rows:
            return False
        _, amount, status = rows[0]

        if status != 'pending':
            return False

        # Current approved total for the department
        rows = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses "
            "WHERE department_id = %s AND status = 'approved'",
            (dept_id,)
        )
        approved_total = rows[0][0] if rows else 0

        # Department budget
        rows = db.execute(
            "SELECT budget FROM departments WHERE id = %s",
            (dept_id,)
        )
        budget = rows[0][0]

        if approved_total + amount <= budget:
            db.execute(
                "UPDATE expenses SET status = 'approved' WHERE id = %s",
                (expense_id,)
            )
            return True
        return False

    return _retry_transaction(db, _run)

def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    def _run(db):
        # Get department_id
        rows = db.execute(
            "SELECT department_id FROM expenses WHERE id = %s",
            (expense_id,)
        )
        if not rows:
            return False
        dept_id = rows[0][0]

        # Lock department row (consistent order: department first)
        db.execute(
            "SELECT * FROM departments WHERE id = %s FOR UPDATE",
            (dept_id,)
        )

        # Lock expense row
        rows = db.execute(
            "SELECT id, amount, status FROM expenses WHERE id = %s FOR UPDATE",
            (expense_id,)
        )
        if not rows:
            return False
        _, old_amount, status = rows[0]

        if status == 'approved':
            # Current approved total for the department
            rows = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses "
                "WHERE department_id = %s AND status = 'approved'",
                (dept_id,)
            )
            approved_total = rows[0][0] if rows else 0

            # Department budget
            rows = db.execute(
                "SELECT budget FROM departments WHERE id = %s",
                (dept_id,)
            )
            budget = rows[0][0]

            new_approved_total = approved_total - old_amount + new_amount
            if new_approved_total <= budget:
                db.execute(
                    "UPDATE expenses SET amount = %s WHERE id = %s",
                    (new_amount, expense_id)
                )
                return True
            return False
        else:
            # Not approved: change is always allowed
            db.execute(
                "UPDATE expenses SET amount = %s WHERE id = %s",
                (new_amount, expense_id)
            )
            return True

    return _retry_transaction(db, _run)

def change_budget(db, dept_id: int, new_budget: int) -> bool:
    def _run(db):
        # Lock department row
        db.execute(
            "SELECT * FROM departments WHERE id = %s FOR UPDATE",
            (dept_id,)
        )

        # Current approved total for the department
        rows = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses "
            "WHERE department_id = %s AND status = 'approved'",
            (dept_id,)
        )
        approved_total = rows[0][0] if rows else 0

        if approved_total <= new_budget:
            db.execute(
                "UPDATE departments SET budget = %s WHERE id = %s",
                (new_budget, dept_id)
            )
            return True
        return False

    return _retry_transaction(db, _run)
