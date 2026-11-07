from psycopg import errors


def migrate(db) -> None:
    pass


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    for _ in range(8):
        try:
            db.begin()

            # Always lock accounts in ascending order of ID to prevent deadlocks
            first_id = min(from_id, to_id)
            second_id = max(from_id, to_id)

            row1 = db.execute(
                "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                (first_id,),
            )
            # If the sender is locked first and lacks funds, exit early
            if first_id == from_id and row1[0][0] < amount:
                db.rollback()
                return False

            row2 = db.execute(
                "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                (second_id,),
            )

            from_balance = row1[0][0] if first_id == from_id else row2[0][0]
            if from_balance < amount:
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
        except (errors.SerializationFailure, errors.DeadlockDetected, errors.LockNotAvailable):
            db.rollback()
            continue

    return False
