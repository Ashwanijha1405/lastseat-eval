import psycopg.errors

def migrate(db) -> None:
    # Partial index to speed up the sum of approved expenses per department
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_expenses_dept_approved
        ON expenses (department_id)
        WHERE status = 'approved'
    """)

def approve_expense(db, expense_id: int) -> bool:
    max_attempts = 3
    for attempt in range(max_attempts):
        db.begin()
        try:
            # Lock the department row and the expense row to serialize approvals for the same department
            rows = db.execute(
                "SELECT d.id, d.budget, e.amount, e.status "
                "FROM departments d "
                "JOIN expenses e ON e.department_id = d.id "
                "WHERE e.id = %s "
                "FOR UPDATE OF d, e",
                (expense_id,)
            )
            if not rows:
                db.rollback()
                return False
            dept_id, budget, amount, status = rows[0]

            if status != 'pending':
                db.rollback()
                return False

            # Current total of already approved expenses in this department
            sum_rows = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses "
                "WHERE department_id = %s AND status = 'approved'",
                (dept_id,)
            )
            current_sum = sum_rows[0][0] if sum_rows else 0

            if current_sum + amount > budget:
                db.rollback()
                return False

            # Approve the expense
            db.execute(
                "UPDATE expenses SET status = 'approved' WHERE id = %s",
                (expense_id,)
            )
            db.commit()
            return True

        except psycopg.errors.DeadlockDetected:
            db.rollback()
            if attempt == max_attempts - 1:
                raise
        except Exception:
            db.rollback()
            raise
    return False
