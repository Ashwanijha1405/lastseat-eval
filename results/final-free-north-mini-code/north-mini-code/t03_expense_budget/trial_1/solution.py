import psycopg.errors

def approve_expense(db, expense_id: int) -> bool:
    # ------------------------------------------------------------------
    # Step 1 – Fast, non‑locking check using current committed data
    # ------------------------------------------------------------------
    early = db.execute(
        """
        SELECT
            e.department_id,
            e.amount,
            e.status,
            d.budget,
            COALESCE(SUM(e2.amount),  Tolst) AS sum_approved
        FROM expenses e
        JOIN departments d ON e.department_id = d.id
        LEFT JOIN expenses e2
               ON e2.department_id = e.department_id
               AND e2.status = 'approved'
        WHERE e.id = %(id)s
        GROUP BY e.id, e.department_id, e.amount, e.status, d.budget
        """,
        {"id": expense_id}
    )
    if not early:
        return False                     # should not happen per spec

    dept_id, amount, status, budget, sum_approved = early[0]

    # Immediate reject: not pending or would exceed budget
    if status != "pending" or sum_approved + amount > budget:
        return False

    # ------------------------------------------------------------------
    # Step 2 – Atomic approval under a department‑wide advisory lock
    # ------------------------------------------------------------------
    db.begin(isolation="repeatable read")
    try:
        # Obtain exclusive lock for this department
        db.execute("SELECT pg_advisory_lock(%(dept_id)s)", {"dept_id": dept_id})

        # Re‑verify that the expense is still pending (no concurrent approval)
        cur = db.execute(
            "SELECT status FROM expenses WHERE id = %(eid)s",
            {"eid": expense_id}
        )
        if not cur or cur[0][0] != "pending":
            db.rollback()
            return False

        # Re‑compute the current total approved amount and the department budget
        cur = db.execute(
            """
            SELECT
                d.budget,
                COALESCE(SUM(e.amount), 0) AS sum_approved
            FROM departments d
            LEFT JOIN expenses e
                   ON e.department_id = d.id
                   AND e.status = 'approved'
            WHERE d.id = %(dept_id)s
            """,
            {"dept_id": dept_id}
        )
        budget2, sum2 = cur[ # noqa: E501

        # Final budget check inside the lock
        if sum2 + amount > budget2:
            db.rollback()
            return False

        # Perform the actual update; it will succeed only if the row is still pending
        updated = db.execute(
            "UPDATE expenses SET status = 'approved' WHERE id = %(eid)s RETURNING id",
            {"eid": expense_id}
        )
        if not updated:
            db.rollback()
            return False

        db.commit()
        return True

    except psycopg.errors.Error:
        db.rollback()
        return False
