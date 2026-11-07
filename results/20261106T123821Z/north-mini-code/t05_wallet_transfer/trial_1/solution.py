from psycopg import errors

def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin()
            # Deterministic locking order to avoid deadlocks
            if from_id < to_id:
                first_id, second_id = from_id, to_id
                first_is_sender = True
            else:
                first_id, second_id = to_id, from_id
                first_is_sender = False

            # Lock both accounts (row-level exclusive locks)
            sender_bal = db.execute(
                "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                (first_id,)
            )[0][0]

            receiver_bal = db.execute(
                "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                (second_id,)
            )[0][0]

            # Adjust if the first locked account is not the sender
            if not first_is_sender:
                sender_bal, receiver_bal = receiver_bal, sender_bal

            if sender_bal >= amount:
                # Perform the transfer atomically
                db.execute(
                    "UPDATE accounts SET balance = %s WHERE id = %s",
                    (sender_bal - amount, from_id)
                )
                db.execute(
                    "UPDATE accounts SET balance = %s WHERE id = %s",
                    (receiver_bal + amount, to_id)
                )
                db.commit()
                return True
            else:
                db.rollback()
                return False

        except errors.SerializationFailure:
            db.rollback()
            continue
        except errors.DeadlockDetected:
            db.rollback()
            continue
        except errors.Error:
            # Any other database error – abort the request
            db.rollback()
            return False
        except Exception:
            # Unexpected Python error – abort and return False
            db.rollback()
            return False

    # Exhausted retry attempts – the request failed
    return False
