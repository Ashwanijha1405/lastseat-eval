import psycopg.errors

def approve_expense(db, expense_id: int) -> bool:
    max_retries = 3
    for _ in range(max_retries):
        try:
            db.begin()
            # Fetch expense details without lock (department_id never changes)
            rows = db.execute(
                "SELECT department_id, amount, status FROM expenses WHERE id = %s",
                (expense_id,)
            )
            if not rows:
                db.rollback()
                return False
            dept_id, amount, status = rows[0]
            if status != 'pending':
                db.rollback()
                return False

            # Lock department row
            dept_rows = db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,)
            )
            budget = dept_rows[0][0]

            # Lock expense row and re-check status/amount
            exp_rows = db.execute(
                "SELECT amount, status FROM expenses WHERE id = %s FOR UPDATE",
                (expense_id,)
            )
            if not exp_rows:
                db.rollback()
                return False
            amount, status = exp_rows[0]
            if status != 'pending':
                db.rollback()
                return False

            # Compute current approved total for the department
            rows = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses "
                "WHERE department_id = %s AND status = 'approved'",
                (dept_id,)
            )
            approved_total = rows[0][0]

            if approved_total + amount <= budget:
                db.execute(
                    "UPDATE expenses SET status = 'approved' WHERE id = %s",
                    (expense_id,)
                )
                db.commit()
                return True
            else:
                db.rollback()
                return False
        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise
    return False


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    max_retries = 3
    for _ in range(max_retries):
        try:
            db.begin()
            # Fetch department_id and status without lock
            rows = db.execute(
                "SELECT department_id, status FROM expenses WHERE id = %s",
                (expense_id,)
            )
            if not rows:
                db.rollback()
                return False
            dept_id, status = rows[0]

            # Lock department row
            dept_rows = db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,)
            )
            budget = dept_rows[0][0]

            # Lock expense row and re-check
            exp_rows = db.execute(
                "SELECT amount, status FROM expenses WHERE id = %s FOR UPDATE",
                (expense_id,)
            )
            if not exp_rows:
                db.rollback()
                return False
            old_amount, status = exp_rows[0]

            if status == 'approved':
                # Compute approved total (includes this expense's old amount)
                rows = db.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM expenses "
                    "WHERE department_id = %s AND status = 'approved'",
                    (dept_id,)
                )
                approved_total = rows[0][0]
                if approved_total - old_amount + new_amount > budget:
                    db.rollback()
                    return False

            # Perform the update
            db.execute(
                "UPDATE expenses SET amount = %s WHERE id = %s",
                (new_amount, expense_id)
            )
            db.commit()
            return True
        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise
    return False


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    max_retries = 3
    for _ in range(max_retries):
        try:
            db.begin()
            # Lock department row
            db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,)
            )
            # Compute approved total
            rows = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses "
                "WHERE department_id = %s AND status = 'approved'",
                (dept_id,)
            )
            approved_total = rows[0][0]

            if approved_total <= new_budget:
                db.execute(
                    "UPDATE departments SET budget = %s WHERE id = %s",
                    (new_budget, dept_id)
                )
                db.commit()
                return True
            else:
                db.rollback()
                return False
        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise
    return False
