"""Checks the balance with a plain SELECT, then moves money with relative updates.

Relative updates keep the total right, but the check may be stale: two
transfers of 40 out of a balance of 50 both pass the check and the balance
ends at -30. Updates in argument order can also deadlock.

EXPECT: safety, liveness
"""


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    db.begin()
    [(balance,)] = db.execute("SELECT balance FROM accounts WHERE id = %s", (from_id,))
    if balance < amount:
        db.rollback()
        return False
    db.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, from_id))
    db.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to_id))
    db.commit()
    return True
