import psycopg.errors as errors

def approve_expense(db, expense_id: int) -> bool:
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin(isolation="repeatable read")

            # Lock the expense row and its department row, fetch needed data.
            row = db.execute("""
                SELECT e.status, e.department_id, d.budget, e.amount
                FROM expenses e
                JOIN departments d ON e.department_id = d.id
                WHERE e.id = %(expense_id)s
                FOR UPDATE
            """, {"expense_id": expense_id})[0]
            status, dept_id, budget, amount = row

            if status != 'pending':
                db.rollback()
                return False

            # Sum of already approved expenses for the department.
            sum_res = db.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM expenses
                WHERE department_id = %(dept_id)s AND status = 'approved'
            """, {"dept_id": dept_id})[0][0]

            if sum_res + amount > budget:
                db.rollback()
                return False

            # Actually approve the expense.
            db.execute("""
                UPDATE expenses
                SET status = 'approved'
                WHERE id = %(expense_id)s
            """, {"expense_id": expense_id})

            db.commit()
            return True

        except (errors.SerializationFailure,
                errors.DeadlockDetected,
                errors.LockNotAvailable):
            try:
                db.rollback()
            except Exception:
                pass
            continue

        except Exception:
            db.rollback()
            raise

    # Fallback if all retries fail (should not happen with correct logic)
    return False

def migrate(db):
    # Optional: create an index to speed up the sum query.
    db.begin()
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_dept_status ON expenses "
        "(department_id, status) INCLUDE (amount)", {}
    )
    db.commit()
