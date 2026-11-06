"""Like the reference, but edit_expense skips the lock for a pending expense.

"A pending expense needs no budget check, so it needs no lock." But the
status it reads can be stale: an approval of the same expense may commit
right after the edit read 'pending'. The edit's UPDATE then waits for the
row, re-checks only `WHERE id = ...` (EvalPlanQual), and raises the amount of
what is now an approved expense with no budget check (counterexample 1).
The other order fails too: the approval reads the old amount, the edit
writes the new one, and the approval's UPDATE then approves the row as it
now is, with an amount no budget check ever saw.

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
    [(status,)] = db.execute("SELECT status FROM expenses WHERE id = %s", (expense_id,))
    if status != "approved":
        db.execute("UPDATE expenses SET amount = %s WHERE id = %s", (new_amount, expense_id))
        db.commit()
        return True
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
    db.execute("SELECT 1 FROM departments WHERE id = %s FOR UPDATE", (dept_id,))
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
