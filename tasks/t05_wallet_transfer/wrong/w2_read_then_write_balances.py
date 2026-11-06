"""Reads both balances, computes new ones in Python, writes them back.

Two transfers out of the same account both read its old balance and both
write old - amount: one debit is lost and money is created. The writes also
happen in argument order, so opposite transfers can deadlock.

EXPECT: safety, liveness
"""


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    db.begin()
    [(src,)] = db.execute("SELECT balance FROM accounts WHERE id = %s", (from_id,))
    [(dst,)] = db.execute("SELECT balance FROM accounts WHERE id = %s", (to_id,))
    if src < amount:
        db.rollback()
        return False
    db.execute("UPDATE accounts SET balance = %s WHERE id = %s", (src - amount, from_id))
    db.execute("UPDATE accounts SET balance = %s WHERE id = %s", (dst + amount, to_id))
    db.commit()
    return True
