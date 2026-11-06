"""Sums approved expenses with a plain SELECT, then approves.

Both requests sum before either has approved, so both see room in the budget.
They update different expense rows, so neither waits for the other, and both
commit: the department ends up over budget.

EXPECT: safety
"""


def approve_expense(db, expense_id: int) -> bool:
    db.begin()
    [(department_id, amount, status)] = db.execute(
        "SELECT department_id, amount, status FROM expenses WHERE id = %s", (expense_id,)
    )
    [(budget,)] = db.execute("SELECT budget FROM departments WHERE id = %s", (department_id,))
    [(approved,)] = db.execute(
        "SELECT COALESCE(sum(amount), 0) FROM expenses WHERE department_id = %s AND status = 'approved'",
        (department_id,),
    )
    if status != "pending" or approved + amount > budget:
        db.rollback()
        return False
    db.execute("UPDATE expenses SET status = 'approved' WHERE id = %s", (expense_id,))
    db.commit()
    return True
