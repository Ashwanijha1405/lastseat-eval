"""Safe conditional debit, then credit, in argument order, with no retry.

The debit is the t01 pattern and never overdraws. But A->B locks A then B
while B->A locks B then A: each can end up holding one row and waiting for
the other. Postgres breaks the cycle by aborting one with DeadlockDetected
(40P01), which escapes as an error for a valid transfer.

EXPECT: liveness
"""


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    db.begin()
    debited = db.execute(
        "UPDATE accounts SET balance = balance - %(amt)s WHERE id = %(id)s AND balance >= %(amt)s RETURNING id",
        {"amt": amount, "id": from_id},
    )
    if not debited:
        db.rollback()
        return False
    db.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to_id))
    db.commit()
    return True
