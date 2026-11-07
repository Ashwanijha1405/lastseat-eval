import psycopg.errors as errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS expenses_dept_status_idx "
        "ON expenses (department_id, status) INCLUDE (amount)"
    )


_RETRYABLE = (
    errors.SerializationFailure,
    errors.DeadlockDetected,
    errors.LockNotAvailable,
)


def approve_expense(db, expense_id: int) -> bool:
    for _ in range(8):
        try:
            db.begin("read committed")
            rows = db.execute(
                "SELECT department_id FROM expenses WHERE id = %s",
                (expense_id,),
            )
            if not rows:
                db.rollback()
                return False
            dept_id = rows[0][0]

            # Serialize all approvals for this department.
            dept = db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR NO KEY UPDATE",
                (dept_id,),
            )
            if not dept:
                db.rollback()
                return False

            # Fresh snapshot (read committed) taken after the lock is held.
            updated = db.execute(
                """
                UPDATE expenses e
                   SET status = 'approved'
                 WHERE e.id = %(eid)s
                   AND e.status = 'pending'
                   AND e.amount + (
                         SELECT COALESCE(SUM(x.amount), 0)
                           FROM expenses x
                          WHERE x.department_id = %(did)s
                            AND x.status = 'approved'
                       ) <= (SELECT d.budget FROM departments d WHERE d.id = %(did)s)
                RETURNING e.id
                """,
                {"eid": expense_id, "did": dept_id},
            )
            db.commit()
            return bool(updated)
        except _RETRYABLE:
            try:
                db.rollback()
            except Exception:
                pass
            continue
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
    return False
