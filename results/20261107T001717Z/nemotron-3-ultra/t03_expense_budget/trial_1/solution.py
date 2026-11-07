import psycopg.errors

def approve_expense(db, expense_id: int) -> bool:
    """
    Approve an expense if it is pending and doing so would not exceed the
    department's budget. Returns True on success, False otherwise.
    """
    # A small retry loop for deadlock/serialization anomalies (should not happen
    # with the locking order used, but kept for robustness).
    max_retries = 5
    for _ in range(max_retries):
        try:
            db.begin()

            # Lock the department row and fetch all data needed for the decision
            # in a single query.
            rows = db.execute(
                """
                SELECT e.department_id, e.amount, d.budget,
                       (SELECT COALESCE(SUM(amount), 0)
                        FROM expenses
                        WHERE department_id = d.id AND status = 'approved') AS approved_sum
                FROM expenses e
                JOIN departments d ON d.id = e.department_id
                WHERE e.id = %s
                FOR UPDATE OF d
                """,
                (expense_id,)
            )

            if not rows:
                db.rollback()
                return False

            dept_id, amount, budget, approved_sum = rows[0]

            # Check budget constraint
            if approved_sum + amount <= budget:
                # Try to approve the expense (only if still pending)
                rows = db.execute(
                    "UPDATE expenses SET status = 'approved' "
                    "WHERE id = %s AND status = 'pending' RETURNING id",
                    (expense_id,)
                )
                if rows:
                    db.commit()
                    return True
                else:
                    db.rollback()
                    return False
            else:
                db.rollback()
                return False

        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise

    # If we somehow exhaust retries (should never happen with correct locking)
    raise RuntimeError("Too many retries due to concurrent conflicts")
