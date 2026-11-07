import psycopg.errors


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    for _ in range(5):
        try:
            db.begin("read committed")
            # Lock both rows in a fixed (id) order so opposite-direction
            # transfers cannot deadlock; the sort happens before row locking.
            rows = db.execute(
                "SELECT id, balance FROM accounts "
                "WHERE id IN (%s, %s) ORDER BY id FOR UPDATE",
                (from_id, to_id),
            )
            balances = {r[0]: r[1] for r in rows}
            if from_id not in balances or to_id not in balances:
                db.rollback()
                return False
            if balances[from_id] < amount:
                db.rollback()
                return False
            db.execute(
                "UPDATE accounts SET balance = balance - %s WHERE id = %s",
                (amount, from_id),
            )
            db.execute(
                "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                (amount, to_id),
            )
            db.commit()
            return True
        except (
            psycopg.errors.SerializationFailure,
            psycopg.errors.DeadlockDetected,
        ):
            db.rollback()
            continue
    return False
