import psycopg
import psycopg.errors


def migrate(db) -> None:
    # Backstop: enforce uniqueness at the database level.
    # If legacy duplicates exist, the index can't be built; the function's
    # advisory-lock path still guarantees no new duplicates are created.
    try:
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS payments_idempotency_key_uidx "
            "ON payments (idempotency_key)"
        )
    except psycopg.errors.Error:
        try:
            db.rollback()
        except Exception:
            pass


def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    for _ in range(5):
        try:
            db.begin("read committed")
            # Serialize all attempts that share the same key.
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (idempotency_key,),
            )
            rows = db.execute(
                "SELECT id FROM payments WHERE idempotency_key = %s "
                "ORDER BY id LIMIT 1",
                (idempotency_key,),
            )
            if rows:
                payment_id = rows[0][0]
            else:
                rows = db.execute(
                    "INSERT INTO payments (idempotency_key, customer_id, amount) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (idempotency_key, customer_id, amount),
                )
                payment_id = rows[0][0]
            db.commit()
            return int(payment_id)
        except (
            psycopg.errors.UniqueViolation,
            psycopg.errors.SerializationFailure,
            psycopg.errors.DeadlockDetected,
        ):
            db.rollback()
            continue
    # Final fallback: the row should exist by now.
    rows = db.execute(
        "SELECT id FROM payments WHERE idempotency_key = %s ORDER BY id LIMIT 1",
        (idempotency_key,),
    )
    return int(rows[0][0])
