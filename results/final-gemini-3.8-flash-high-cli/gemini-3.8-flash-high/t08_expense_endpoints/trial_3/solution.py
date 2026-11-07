import psycopg.errors


def approve_expense(db, expense_id: int) -> bool:
    for attempt in range(8):
        try:
            db.begin("read committed")
            dept_res = db.execute(
                "SELECT department_id FROM expenses WHERE id = %(id)s",
                {"id": expense_id},
            )
            dept_id = dept_res[0][0]

            db.execute(
                "SELECT pg_advisory_xact_lock(%(dept_id)s)",
                {"dept_id": dept_id},
            )

            row = db.execute(
                """
                SELECT
                    d.budget,
                    e.amount,
                    e.status,
                    (SELECT COALESCE(SUM(amount), 0)
                     FROM expenses
                     WHERE department_id = %(dept_id)s AND status = 'approved') AS approved_total
                FROM departments d, expenses e
                WHERE d.id = %(dept_id)s AND e.id = %(id)s
                """,
                {"dept_id": dept_id, "id": expense_id},
            )
            budget, amount, status, approved_total = row[0]

            if status == "pending" and approved_total + amount <= budget:
                db.execute(
                    "UPDATE expenses SET status = 'approved' WHERE id = %(id)s",
                    {"id": expense_id},
                )
                db.commit()
                return True
            else:
                db.commit()
                return False
        except psycopg.errors.Error:
            try:
                db.rollback()
            except Exception:
                pass
            if attempt == 7:
                raise
    return False


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    for attempt in range(8):
        try:
            db.begin("read committed")
            dept_res = db.execute(
                "SELECT department_id FROM expenses WHERE id = %(id)s",
                {"id": expense_id},
            )
            dept_id = dept_res[0][0]

            db.execute(
                "SELECT pg_advisory_xact_lock(%(dept_id)s)",
                {"dept_id": dept_id},
            )

            row = db.execute(
                """
                SELECT
                    d.budget,
                    e.status,
                    (SELECT COALESCE(SUM(amount), 0)
                     FROM expenses
                     WHERE department_id = %(dept_id)s AND status = 'approved' AND id != %(id)s) AS other_approved
                FROM departments d, expenses e
                WHERE d.id = %(dept_id)s AND e.id = %(id)s
                """,
                {"dept_id": dept_id, "id": expense_id},
            )
            budget, status, other_approved = row[0]

            if status == "approved":
                if other_approved + new_amount <= budget:
                    db.execute(
                        "UPDATE expenses SET amount = %(new_amount)s WHERE id = %(id)s",
                        {"new_amount": new_amount, "id": expense_id},
                    )
                    db.commit()
                    return True
                else:
                    db.commit()
                    return False
            else:
                db.execute(
                    "UPDATE expenses SET amount = %(new_amount)s WHERE id = %(id)s",
                    {"new_amount": new_amount, "id": expense_id},
                )
                db.commit()
                return True
        except psycopg.errors.Error:
            try:
                db.rollback()
            except Exception:
                pass
            if attempt == 7:
                raise
    return False


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    for attempt in range(8):
        try:
            db.begin("read committed")
            db.execute(
                "SELECT pg_advisory_xact_lock(%(dept_id)s)",
                {"dept_id": dept_id},
            )

            row = db.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS approved_total
                FROM expenses
                WHERE department_id = %(dept_id)s AND status = 'approved'
                """,
                {"dept_id": dept_id},
            )
            approved_total = row[0][0]

            if approved_total <= new_budget:
                db.execute(
                    "UPDATE departments SET budget = %(new_budget)s WHERE id = %(dept_id)s",
                    {"new_budget": new_budget, "dept_id": dept_id},
                )
                db.commit()
                return True
            else:
                db.commit()
                return False
        except psycopg.errors.Error:
            try:
                db.rollback()
            except Exception:
                pass
            if attempt == 7:
                raise
    return False
