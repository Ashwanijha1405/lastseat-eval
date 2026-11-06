"""Locks the department's approved expenses with FOR UPDATE and sums them in Python.

The expense the other request is approving is still pending when this query
runs, so it is not in the result and never gets locked. With nothing approved
yet, the query locks no rows at all. With one approved expense, both requests
lock it and take turns, but after waiting Postgres only re-checks the rows
this query was waiting on; the newly approved row is still missing from the
result, so the Python sum is stale.

EXPECT: safety
"""


def approve_expense(db, expense_id: int) -> bool:
    db.begin()
    [(department_id, amount, status)] = db.execute(
        "SELECT department_id, amount, status FROM expenses WHERE id = %s", (expense_id,)
    )
    [(budget,)] = db.execute("SELECT budget FROM departments WHERE id = %s", (department_id,))
    rows = db.execute(
        "SELECT amount FROM expenses WHERE department_id = %s AND status = 'approved' FOR UPDATE",
        (department_id,),
    )
    approved = sum(r[0] for r in rows)
    if status != "pending" or approved + amount > budget:
        db.rollback()
        return False
    db.execute("UPDATE expenses SET status = 'approved' WHERE id = %s", (expense_id,))
    db.commit()
    return True
