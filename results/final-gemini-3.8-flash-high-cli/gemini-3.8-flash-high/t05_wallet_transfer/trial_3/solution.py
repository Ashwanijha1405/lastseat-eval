from psycopg import errors

RETRIABLE_EXCEPTIONS = tuple(
    exc
    for exc in (
        getattr(errors, "SerializationFailure", None),
        getattr(errors, "DeadlockDetected", None),
        getattr(errors, "LockNotAvailable", None),
        getattr(errors, "OperationalError", None),
    )
    if exc is not None
)


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    first_id = min(from_id, to_id)
    second_id = max(from_id, to_id)

    for _ in range(8):
        try:
            db.begin()

            # Lock the lower-numbered account first
            r1 = db.execute(
                "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                (first_id,),
            )

            if from_id == first_id:
                # Sender is first_id; check balance before locking second_id
                if r1[0][0] < amount:
                    db.rollback()
                    return False
                db.execute(
                    "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                    (second_id,),
                )
            else:
                # Receiver is first_id; lock sender (second_id) and check balance
                r2 = db.execute(
                    "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                    (second_id,),
                )
                if r2[0][0] < amount:
                    db.rollback()
                    return False

            # Transfer amount between accounts in a single statement
            db.execute(
                "UPDATE accounts SET balance = balance + CASE "
                "WHEN id = %s THEN %s ELSE %s END "
                "WHERE id IN (%s, %s)",
                (to_id, amount, -amount, from_id, to_id),
            )
            db.commit()
            return True

        except RETRIABLE_EXCEPTIONS:
            try:
                db.rollback()
            except Exception:
                pass
            continue

    return False
