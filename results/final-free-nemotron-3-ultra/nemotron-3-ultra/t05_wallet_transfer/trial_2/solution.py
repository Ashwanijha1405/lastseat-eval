import psycopg.errors

def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    """
    Transfer `amount` from `from_id` to `to_id`.
    Returns True on success, False if sender has insufficient funds.
    """
    # Lock accounts in a consistent order (by id) to avoid deadlocks.
    first, second = sorted((from_id, to_id))
    max_retries = 10  # enough for any realistic contention; stays within 60 db calls

    for _ in range(max_retries + 1):
        db.begin()
        try:
            # Lock and read the first account
            rows = db.execute(
                "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                (first,)
            )
            balance_first = rows[0][0]

            # Lock and read the second account
            rows = db.execute(
                "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                (second,)
            )
            balance_second = rows[0][0]

            # Determine sender / receiver balances
            if first == from_id:
                sender_balance = balance_first
                receiver_balance = balance_second
            else:
                sender_balance = balance_second
                receiver_balance = balance_first

            # Insufficient funds -> roll back and retry (another concurrent transfer may add funds)
            if sender_balance < amount:
                db.rollback()
                continue

            # Perform the transfer
            new_sender = sender_balance - amount
            new_receiver = receiver_balance + amount

            if first == from_id:
                db.execute(
                    "UPDATE accounts SET balance = %s WHERE id = %s",
                    (new_sender, first)
                )
                db.execute(
                    "UPDATE accounts SET balance = %s WHERE id = %s",
                    (new_receiver, second)
                )
            else:
                db.execute(
                    "UPDATE accounts SET balance = %s WHERE id = %s",
                    (new_sender, second)
                )
                db.execute(
                    "UPDATE accounts SET balance = %s WHERE id = %s",
                    (new_receiver, first)
                )

            db.commit()
            return True

        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            # Should not happen with consistent lock order, but retry if it does.
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise

    return False


def migrate(db) -> None:
    """
    Optional migration: add a check constraint to guarantee balances never go negative.
    Runs once before any requests.
    """
    db.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'accounts_balance_nonnegative'
            ) THEN
                ALTER TABLE accounts ADD CONSTRAINT accounts_balance_nonnegative CHECK (balance >= 0);
            END IF;
        END $$;
    """)
