"""Reference: every function locks the department row first, then reads.

All three functions can change a department's approved total or its budget,
so all three take the same lock: the department row (FOR UPDATE). Requests
for one department therefore take turns, whichever functions they call;
requests for different departments run in parallel. Each function reads
status / amount / approved total in a new statement after the lock is
granted, so under READ COMMITTED it sees everything committed by whoever
held the lock before. One lock per request, so no deadlock is possible.

edit_expense takes the lock even for a pending expense: an approval running
at the same moment may have read the old amount and be about to approve it.
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
