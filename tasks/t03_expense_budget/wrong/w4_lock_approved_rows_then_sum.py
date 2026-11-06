"""Locks the approved expenses with FOR UPDATE, then sums in a fresh statement.

When at least one expense is already approved, both requests lock it, take
turns, and the later SUM (a new READ COMMITTED snapshot) sees the other
approval: safe by accident. When nothing is approved yet, the FOR UPDATE
locks no rows, nobody waits, and both approvals go through.

EXPECT: safety
"""


def approve_expense(db, expense_id: int) -> bool:
    db.begin()
    [(department_id, amount, status)] = db.execute(
        "SELECT department_id, amount, status FROM expenses WHERE id = %s", (expense_id,)
    )
    db.execute(
        "SELECT id FROM expenses WHERE department_id = %s AND status = 'approved' FOR UPDATE",
        (department_id,),
    )
    [(budget, approved)] = db.execute(
        "SELECT d.budget, COALESCE(sum(e.amount), 0) FROM departments d"
        " LEFT JOIN expenses e ON e.department_id = d.id AND e.status = 'approved'"
        " WHERE d.id = %s GROUP BY d.budget",
        (department_id,),
    )
    if status != "pending" or approved + amount > budget:
        db.rollback()
        return False
    db.execute("UPDATE expenses SET status = 'approved' WHERE id = %s", (expense_id,))
    db.commit()
    return True
