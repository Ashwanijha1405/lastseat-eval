"""Reference: lock both accounts in id order, then check and move the money.

Every transfer locks the lower id first, so two transfers touching the same
accounts can never each hold one lock while waiting for the other (no
deadlock). FOR UPDATE with ORDER BY locks rows after sorting, and under READ
COMMITTED returns the newest committed balance after any wait, so the balance
check is current. Relative updates keep the total unchanged.
"""


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    db.begin()
    rows = db.execute(
        "SELECT id, balance FROM accounts WHERE id IN (%s, %s) ORDER BY id FOR UPDATE",
        (from_id, to_id),
    )
    balance = dict(rows)[from_id]
    if balance < amount:
        db.rollback()
        return False
    db.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, from_id))
    db.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to_id))
    db.commit()
    return True
