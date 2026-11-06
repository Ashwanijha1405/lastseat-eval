"""SERIALIZABLE with a bounded retry, but only on SerializationFailure (40001).

SERIALIZABLE keeps the data correct. But two UPDATEs waiting on each other's
row locks are a real lock deadlock, which Postgres reports as
DeadlockDetected (40P01) even at SERIALIZABLE. That error is not retried and
reaches the caller.

EXPECT: liveness
"""

import psycopg.errors


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    for _ in range(10):
        try:
            db.begin("serializable")
            [(balance,)] = db.execute("SELECT balance FROM accounts WHERE id = %s", (from_id,))
            if balance < amount:
                db.rollback()
                return False
            db.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, from_id))
            db.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to_id))
            db.commit()
            return True
        except psycopg.errors.SerializationFailure:
            db.rollback()
    return False
