import psycopg.errors as errors

_RETRYABLE = (
    errors.DeadlockDetected,
    errors.SerializationFailure,
    errors.LockNotAvailable,
)


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    last_exc = None
    for _ in range(6):
        db.begin("read committed")
        try:
            # Lock both rows in a global order (ascending id) to avoid deadlocks.
            rows = db.execute(
                "SELECT id, balance FROM accounts "
                "WHERE id IN (%(a)s, %(b)s) "
                "ORDER BY id FOR UPDATE",
                {"a": from_id, "b": to_id},
            )
            balances = {r[0]: r[1] for r in rows}
            if balances.get(from_id) is None or balances.get(to_id) is None \
                    or balances[from_id] < amount:
                db.rollback()
                return False

            db.execute(
                "UPDATE accounts SET balance = balance + CASE "
                "WHEN id = %(f)s THEN -%(amt)s ELSE %(amt)s END "
                "WHERE id IN (%(f)s, %(t)s)",
                {"f": from_id, "t": to_id, "amt": amount},
            )
            db.commit()
            return True
        except _RETRYABLE as e:
            last_exc = e
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise
    raise last_exc
