from __future__ import annotations

from psycopg import errors


def approve_expense(db, expense_id: int) -> bool:
    for attempt in range(10):
        try:
            db.begin(isolation="read committed")
            rows = db.execute(
                "SELECT department_id, status FROM expenses WHERE id = %s",
                (expense_id,),
            )
            if not rows:
                db.rollback()
                return False
            dept_id, status = rows[0]
            if status != "pending":
                db.rollback()
                return False

            dept_rows = db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,),
            )
            if not dept_rows:
                db.rollback()
                return False
            budget = dept_rows[0][0]

            update_rows = db.execute(
                """
                UPDATE expenses
                SET status = 'approved'
                WHERE id = %(expense_id)s
                  AND status = 'pending'
                  AND amount + (
                      SELECT COALESCE(SUM(sub.amount), 0)
                      FROM expenses sub
                      WHERE sub.department_id = %(dept_id)s
                        AND sub.status = 'approved'
                  ) <= %(budget)s
                RETURNING id
                """,
                {
                    "expense_id": expense_id,
                    "dept_id": dept_id,
                    "budget": budget,
                },
            )
            db.commit()
            return len(update_rows) > 0
        except (errors.SerializationFailure, errors.DeadlockDetected, errors.TransactionRollbackError):
            try:
                db.rollback()
            except Exception:
                pass
            continue
    return False


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    for attempt in range(10):
        try:
            db.begin(isolation="read committed")
            rows = db.execute(
                "SELECT department_id FROM expenses WHERE id = %s",
                (expense_id,),
            )
            if not rows:
                db.rollback()
                return False
            dept_id = rows[0][0]

            dept_rows = db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,),
            )
            if not dept_rows:
                db.rollback()
                return False
            budget = dept_rows[0][0]

            update_rows = db.execute(
                """
                UPDATE expenses
                SET amount = %(new_amount)s
                WHERE id = %(expense_id)s
                  AND (
                      status <> 'approved'
                      OR (
                          status = 'approved'
                          AND %(new_amount)s + (
                              SELECT COALESCE(SUM(sub.amount), 0)
                              FROM expenses sub
                              WHERE sub.department_id = %(dept_id)s
                                AND sub.status = 'approved'
                                AND sub.id <> %(expense_id)s
                          ) <= %(budget)s
                      )
                  )
                RETURNING id
                """,
                {
                    "expense_id": expense_id,
                    "new_amount": new_amount,
                    "dept_id": dept_id,
                    "budget": budget,
                },
            )
            db.commit()
            return len(update_rows) > 0
        except (errors.SerializationFailure, errors.DeadlockDetected, errors.TransactionRollbackError):
            try:
                db.rollback()
            except Exception:
                pass
            continue
    return False


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    for attempt in range(10):
        try:
            db.begin(isolation="read committed")
            dept_rows = db.execute(
                "SELECT budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,),
            )
            if not dept_rows:
                db.rollback()
                return False

            update_rows = db.execute(
                """
                UPDATE departments
                SET budget = %(new_budget)s
                WHERE id = %(dept_id)s
                  AND (
                      SELECT COALESCE(SUM(sub.amount), 0)
                      FROM expenses sub
                      WHERE sub.department_id = %(dept_id)s
                        AND sub.status = 'approved'
                  ) <= %(new_budget)s
                RETURNING id
                """,
                {
                    "dept_id": dept_id,
                    "new_budget": new_budget,
                },
            )
            db.commit()
            return len(update_rows) > 0
        except (errors.SerializationFailure, errors.DeadlockDetected, errors.TransactionRollbackError):
            try:
                db.rollback()
            except Exception:
                pass
            continue
    return False
