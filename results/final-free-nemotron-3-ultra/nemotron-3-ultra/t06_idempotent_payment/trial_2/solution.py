import psycopg.errors

def migrate(db) -> None:
    # Add a unique constraint on idempotency_key to enforce rule 1 at the database level.
    db.execute(
        "ALTER TABLE payments ADD CONSTRAINT IF NOT EXISTS "
        "payments_idempotency_key_unique UNIQUE (idempotency_key)"
    )

def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    """
    Creates a payment for the given idempotency key.
    If a payment with the same key already exists, returns its id.
    """
    try:
        # Try to insert the new payment. If the key is unique, this succeeds and returns the new id.
        rows = db.execute(
            "INSERT INTO payments (idempotency_key, customer_id, amount) "
            "VALUES (%s, %s, %s) RETURNING id",
            (idempotency_key, customer_id, amount)
        )
        return rows[0][0]
    except psycopg.errors.UniqueViolation:
        # Another concurrent request already inserted the same key.
        # The unique constraint guarantees the row exists and is committed.
        rows = db.execute(
            "SELECT id FROM payments WHERE idempotency_key = %s",
            (idempotency_key,)
        )
        return rows[0][0]
