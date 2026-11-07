import psycopg.errors


def approve_expense(db, expense_id: int) -> bool:
    for _ in range(5):
        try:
            db.begin("read committed")

            # department_id never changes, so reading it without a lock is safe.
            rows = db.execute(
                "SELECT department_id FROM expenses WHERE id = %s",
                (expense_id,),
            )
            if not rows:
                db.rollback()
                return False
            dept_id = rows[0][0]

            # Serialize all approvals for this department. In READ COMMITTED,
            # each later statement takes a fresh snapshot, so after acquiring
            # this lock we see every previously committed approval.
            budget_rows = db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,),
            )
            budget = budget_rows[0][0]

            updated = db.execute(
                """
                UPDATE expenses
                   SET status = 'approved'
                 WHERE id = %(eid)s
                   AND status = 'pending'
                   AND amount + (
                         SELECT COALESCE(SUM(amount), 0)
                           FROM expenses
                          WHERE department_id = %(did)s
                            AND status = 'approved'
                       ) <= %(budget)s
                RETURNING id
                """,
                {"eid": expense_id, "did": dept_id, "budget": budget},
            )
            db.commit()
            return bool(updated)
        except (
            psycopg.errors.DeadlockDetected,
            psycopg.errors.SerializationFailure,
        ):
            db.rollback()
            continue
    return False
