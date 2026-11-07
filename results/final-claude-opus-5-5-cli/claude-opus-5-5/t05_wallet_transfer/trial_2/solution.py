import psycopg.errors


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    lo, hi = (from_id, to_id) if from_id < to_id else (to_id, from_id)

    for _ in range(10):
        try:
            db.begin("read committed")
            # Lock both rows in a deterministic order (by id) to avoid deadlocks.
            rows = db.execute(
                "SELECT id, balance FROM accounts "
                "WHERE id IN (%(lo)s, %(hi)s) ORDER BY id FOR UPDATE",
                {"lo": lo, "hi": hi},
            )
            balances = {r[0]: r[1] for r in rows}
            if balances.get(from_id, 0) < amount:
                db.rollback()
                return False

            db.execute(
                "UPDATE accounts SET balance = balance + "
                "CASE WHEN id = %(f)s THEN -%(a)s ELSE %(a)s END "
                "WHERE id IN (%(f)s, %(t)s)",
                {"f": from_id, "t": to_id, "a": amount},
            )
            db.commit()
            return True
        except (
            psycopg.errors.DeadlockDetected,
            psycopg.errors.SerializationFailure,
            psycopg.errors.LockNotAvailable,
        ):
            try:
                db.rollback()
            except Exception:
                pass
            continue

    # Extremely unlikely: give a final attempt without catching, so failures surface.
    db.begin("read committed")
    rows = db.execute(
        "SELECT id, balance FROM accounts "
        "WHERE id IN (%(lo)s, %(hi)s) ORDER BY id FOR UPDATE",
        {"lo": lo, "hi": hi},
    )
    balances = {r[0]: r[1] for r in rows}
    if balances.get(from_id, 0) < amount:
        db.rollback()
        return False
    db.execute(
        "UPDATE accounts SET balance = balance + "
        "CASE WHEN id = %(f)s THEN -%(a)s ELSE %(a)s END "
        "WHERE id IN (%(f)s, %(t)s)",
        {"f": from_id, "t": to_id, "a": amount},
    )
    db.commit()
    return True
