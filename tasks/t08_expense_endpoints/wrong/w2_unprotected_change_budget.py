"""Approve and edit lock the department row; change_budget checks without it.

change_budget sums the approved expenses first and only then updates the
department row. The sum can be stale by then: an approval that held the
department lock commits in between (counterexample 1). If the approval is
still running, the UPDATE waits for its lock, but on resuming Postgres
re-checks only `WHERE id = ...` on the department row (EvalPlanQual), never
the total read earlier. Either way the cut lands below the approved total.

EXPECT: safety
"""

_LOCK_DEPARTMENT_OF_EXPENSE = (
    "SELECT budget FROM departments"
    " WHERE id = (SELECT department_id FROM expenses WHERE id = %s) FOR UPDATE"
)
_READ_EXPENSE_AND_TOTAL = (
    "SELECT e.status, e.amount,"
    " (SELECT COALESCE(sum(a.amount), 0) FROM expenses a"
    "  WHERE a.department_id = e.department_id AND a.status = 'approved')"
    " FROM expenses e WHERE e.id = %s"
)


def approve_expense(db, expense_id: int) -> bool:
    db.begin()
    [(budget,)] = db.execute(_LOCK_DEPARTMENT_OF_EXPENSE, (expense_id,))
    [(status, amount, approved)] = db.execute(_READ_EXPENSE_AND_TOTAL, (expense_id,))
    if status != "pending" or approved + amount > budget:
        db.rollback()
        return False
    db.execute("UPDATE expenses SET status = 'approved' WHERE id = %s", (expense_id,))
    db.commit()
    return True


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    db.begin()
    [(budget,)] = db.execute(_LOCK_DEPARTMENT_OF_EXPENSE, (expense_id,))
    [(status, amount, approved)] = db.execute(_READ_EXPENSE_AND_TOTAL, (expense_id,))
    if status == "approved" and approved - amount + new_amount > budget:
        db.rollback()
        return False
    db.execute("UPDATE expenses SET amount = %s WHERE id = %s", (new_amount, expense_id))
    db.commit()
    return True


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    db.begin()
    [(approved,)] = db.execute(
        "SELECT COALESCE(sum(amount), 0) FROM expenses WHERE department_id = %s AND status = 'approved'",
        (dept_id,),
    )
    if approved > new_budget:
        db.rollback()
        return False
    db.execute("UPDATE departments SET budget = %s WHERE id = %s", (new_budget, dept_id))
    db.commit()
    return True
