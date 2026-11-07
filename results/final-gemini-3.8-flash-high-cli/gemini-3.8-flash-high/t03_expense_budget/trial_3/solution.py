from __future__ import annotations

import psycopg.errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_approved "
        "ON expenses (department_id, amount) WHERE status = 'approved'"
    )


def approve_expense(db, expense_id: int) -> bool:
    for _ in range(5):
        try:
            db.begin()

            # Serialize approval requests per department using a transaction-level advisory lock.
            # Any concurrent request for the same department will wait until this transaction finishes.
            lock_rows = db.execute(
                "SELECT pg_advisory_xact_lock(department_id::bigint) "
                "FROM expenses WHERE id = %(id)s",
                {"id": expense_id},
            )
            if not lock_rows:
                db.rollback()
                return False

            # With the department lock acquired, read committed ensures this statement sees
            # all previously committed approvals. Fetch current status, amount, department budget,
            # and current sum of approved expenses.
            rows = db.execute(
                """
                SELECT
                    e.status,
                    e.amount,
                    d.budget,
                    COALESCE((
                        SELECT SUM(amount)
                        FROM expenses
                        WHERE department_id = e.department_id AND status = 'approved'
                    ), 0) AS total_approved
                FROM expenses e
                JOIN departments d ON d.id = e.department_id
                WHERE e.id = %(id)s
                """,
                {"id": expense_id},
            )
            if not rows:
                db.rollback()
                return False

            status, amount, budget, total_approved = rows[0]

            if status != "pending" or total_approved + amount > budget:
                db.rollback()
                return False

            db.execute(
                "UPDATE expenses SET status = 'approved' "
                "WHERE id = %(id)s AND status = 'pending'",
                {"id": expense_id},
            )
            db.commit()
            return True

        except psycopg.errors.Error:
            try:
                db.rollback()
            except Exception:
                pass
            continue

    return False
