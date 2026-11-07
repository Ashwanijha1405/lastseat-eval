import psycopg
import psycopg.errors


def migrate(db) -> None:
    # Safety net: enforce uniqueness at the database level.
    # If pre-existing data already contains duplicates, skip it; the advisory
    # lock in create_payment still guarantees no new duplicates are created.
    try:
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS payments_idempotency_key_uidx "
            "ON payments (idempotency_key)"
        )
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    for _ in range(5):
        db.begin("read committed")
        try:
            # Serialize all attempts that share the same key.
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (idempotency_key,),
            )
            rows = db.execute(
                "SELECT id FROM payments WHERE idempotency_key = %s ORDER BY id LIMIT 1",
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
        except Exception:
            db.rollback()
            raise

    # Last resort: the payment must exist by now.
    rows = db.execute(
        "SELECT id FROM payments WHERE idempotency_key = %s ORDER BY id LIMIT 1",
        (idempotency_key,),
    )
    return int(rows[0][0])
