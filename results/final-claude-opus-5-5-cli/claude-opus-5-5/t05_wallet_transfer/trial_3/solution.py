import psycopg.errors as errors

_RETRYABLE = (errors.SerializationFailure, errors.DeadlockDetected)


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    for _ in range(8):
        try:
            db.begin("read committed")
            # Lock both rows in a consistent (id) order to prevent deadlocks.
            rows = db.execute(
                "SELECT id, balance FROM accounts "
                "WHERE id IN (%(a)s, %(b)s) ORDER BY id FOR UPDATE",
                {"a": from_id, "b": to_id},
            )
            balances = {r[0]: r[1] for r in rows}
            if balances.get(from_id) is None or balances[from_id] < amount:
                db.rollback()
                return False
            res = db.execute(
                "UPDATE accounts SET balance = balance + CASE WHEN id = %(f)s "
                "THEN -%(amt)s ELSE %(amt)s END "
                "WHERE id IN (%(f)s, %(t)s) "
                "AND (id <> %(f)s OR balance >= %(amt)s) "
                "RETURNING id",
                {"f": from_id, "t": to_id, "amt": amount},
            )
            if len(res) != 2:
                db.rollback()
                return False
            db.commit()
            return True
        except _RETRYABLE:
            try:
                db.rollback()
            except Exception:
                pass
            continue
    return False
