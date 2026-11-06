"""Reference: lock the department row, then read and sum in a fresh statement.

Every approval for a department locks the same department row, so approvals
for one department take turns, while approvals for different departments run
in parallel. Under READ COMMITTED each statement takes a fresh snapshot, so
the read that runs after the lock is granted sees every approval committed by
whoever held the lock before. One lock per request, so no deadlock is
possible. (FOR UPDATE locks only the departments row, not the expenses read
in the subquery.)
"""


def approve_expense(db, expense_id: int) -> bool:
    db.begin()
    [(budget,)] = db.execute(
        "SELECT budget FROM departments"
        " WHERE id = (SELECT department_id FROM expenses WHERE id = %s) FOR UPDATE",
        (expense_id,),
    )
    [(status, amount, approved)] = db.execute(
        "SELECT e.status, e.amount,"
        " (SELECT COALESCE(sum(a.amount), 0) FROM expenses a"
        "  WHERE a.department_id = e.department_id AND a.status = 'approved')"
        " FROM expenses e WHERE e.id = %s",
        (expense_id,),
    )
    if status != "pending" or approved + amount > budget:
        db.rollback()
        return False
    db.execute("UPDATE expenses SET status = 'approved' WHERE id = %s", (expense_id,))
    db.commit()
    return True
