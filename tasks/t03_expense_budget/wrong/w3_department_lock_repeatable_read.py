"""The reference's department lock, but under REPEATABLE READ.

REPEATABLE READ takes its snapshot at the transaction's first statement and
keeps it. Here that statement is the department FOR UPDATE, which may wait
for another approval to commit; the snapshot was already taken before the
wait. The other transaction only locked the department row (it did not
change it), so Postgres grants the lock without a serialization error, and
the SUM afterwards still uses the old snapshot that does not include the
other approval.

EXPECT: safety
"""


def approve_expense(db, expense_id: int) -> bool:
    db.begin("repeatable read")
    [(budget,)] = db.execute(
        "SELECT budget FROM departments"
        " WHERE id = (SELECT department_id FROM expenses WHERE id = %s) FOR UPDATE",
        (expense_id,),
    )
    [(department_id, amount, status)] = db.execute(
        "SELECT department_id, amount, status FROM expenses WHERE id = %s", (expense_id,)
    )
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
