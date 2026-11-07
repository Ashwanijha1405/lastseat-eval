from __future__ import annotations

from psycopg import errors


def approve_expense(db, expense_id: int) -> bool:
    dept_rows = db.execute(
        "SELECT department_id FROM expenses WHERE id = %s",
        (expense_id,),
    )
    dept_id = dept_rows[0][0]

    for attempt in range(10):
        try:
            db.begin()
            budget_rows = db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,),
            )
            budget = budget_rows[0][0]

            expense_rows = db.execute(
                """
                SELECT
                    amount,
                    status,
                    (SELECT COALESCE(SUM(amount), 0)
                     FROM expenses
                     WHERE department_id = %(dept_id)s AND status = 'approved') AS approved_total
                FROM expenses
                WHERE id = %(expense_id)s
                """,
                {"dept_id": dept_id, "expense_id": expense_id},
            )
            amount, status, approved_total = expense_rows[0]

            if status != "pending" or approved_total + amount > budget:
                db.rollback()
                return False

            db.execute(
                "UPDATE expenses SET status = 'approved' WHERE id = %s",
                (expense_id,),
            )
            db.commit()
            return True
        except errors.Error:
            try:
                db.rollback()
            except errors.Error:
                pass
            if attempt == 9:
                raise


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    dept_rows = db.execute(
        "SELECT department_id FROM expenses WHERE id = %s",
        (expense_id,),
    )
    dept_id = dept_rows[0][0]

    for attempt in range(10):
        try:
            db.begin()
            budget_rows = db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,),
            )
            budget = budget_rows[0][0]

            expense_rows = db.execute(
                """
                SELECT
                    amount,
                    status,
                    (SELECT COALESCE(SUM(amount), 0)
                     FROM expenses
                     WHERE department_id = %(dept_id)s AND status = 'approved') AS approved_total
                FROM expenses
                WHERE id = %(expense_id)s
                """,
                {"dept_id": dept_id, "expense_id": expense_id},
            )
            current_amount, status, approved_total = expense_rows[0]

            if status == "approved":
                new_approved_total = approved_total - current_amount + new_amount
                if new_approved_total > budget:
                    db.rollback()
                    return False

            db.execute(
                "UPDATE expenses SET amount = %(new_amount)s WHERE id = %(expense_id)s",
                {"new_amount": new_amount, "expense_id": expense_id},
            )
            db.commit()
            return True
        except errors.Error:
            try:
                db.rollback()
            except errors.Error:
                pass
            if attempt == 9:
                raise


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    for attempt in range(10):
        try:
            db.begin()
            db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,),
            )
            total_rows = db.execute(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM expenses
                WHERE department_id = %s AND status = 'approved'
                """,
                (dept_id,),
            )
            approved_total = total_rows[0][0]

            if approved_total > new_budget:
                db.rollback()
                return False

            db.execute(
                "UPDATE departments SET budget = %s WHERE id = %s",
                (new_budget, dept_id),
            )
            db.commit()
            return True
        except errors.Error:
            try:
                db.rollback()
            except errors.Error:
                pass
            if attempt == 9:
                raise
