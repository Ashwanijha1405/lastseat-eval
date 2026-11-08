from psycopg import errors

def migrate(db):
    # No schema changes needed for this scenario.
    pass

def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    MAX_ATTEMPTS = 10
    for _ in range(MAX_ATTEMPTS):
        try:
            db.begin(isolation="serializable")

            # Determine lock order: always lock the smaller id first to avoid deadlocks
            low, high = (from_id, to_id) if from_id < to_id else (to_id, from_id)

            # Lock both rows and fetch their balances in one statement each
            low_row = db.execute(
                "SELECT id, balance FROM accounts WHERE id = %(id)s FOR UPDATE",
                {"id": low}
            )[0]
            high_row = db.execute(
                "SELECT id, balance FROM accounts WHERE id = %(id)s FOR UPDATE",
                {"id": high}
            )[0]

            balances = {low_row[0]: low_row[1], high_row[0]: high_row[1]}
            from_balance = balances[from_id]

            if from_balance >= amount:
                db.execute(
                    "UPDATE accounts SET balance = balance - %(amt)s WHERE id = %(id)s",
                    {"amt": amount, "id": from_id}
                )
                db.execute(
                    "UPDATE accounts SET balance = balance + %(amt)s WHERE id = %(id)s",
                    {"amt": amount, "id": to_id}
                )
                db.commit()
                return True
            else:
                db.rollback()
                return False
        except (errors.DeadlockDetected, errors.SerializationFailure):
            db.rollback()
            continue
    # If we exhausted attempts without success, raise an error (should not happen in correct runs)
    raise RuntimeError("Transfer failed after retries")
