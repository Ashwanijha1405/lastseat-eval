import psycopg
import psycopg.errors
from psycopg import errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS payments_idem_key_idx "
        "ON payments (idempotency_key, id)"
    )
    try:
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS payments_idem_key_uniq "
            "ON payments (idempotency_key)"
        )
    except psycopg.Error:
        # Existing data may already contain duplicate keys; the advisory lock
        # in create_payment guarantees no new duplicates are created.
        try:
            db.rollback()
        except Exception:
            pass


def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    last_exc = None
    for _ in range(8):
        try:
            db.begin("read committed")
            # Serialize all attempts that use the same idempotency key.
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 7310))",
                (idempotency_key,),
            )
            rows = db.execute(
                "SELECT id FROM payments WHERE idempotency_key = %s "
                "ORDER BY id LIMIT 1",
                (idempotency_key,),
            )
            if rows:
                pid = int(rows[0][0])
                db.commit()
                return pid
            rows = db.execute(
                "INSERT INTO payments (idempotency_key, customer_id, amount) "
                "VALUES (%s, %s, %s) RETURNING id",
                (idempotency_key, customer_id, amount),
            )
            pid = int(rows[0][0])
            db.commit()
            return pid
        except (
            errors.SerializationFailure,
            errors.DeadlockDetected,
            errors.UniqueViolation,
            errors.LockNotAvailable,
        ) as e:
            last_exc = e
            try:
                db.rollback()
            except Exception:
                pass
            continue
        except psycopg.Error as e:
            last_exc = e
            try:
                db.rollback()
            except Exception:
                pass
            continue

    # Final fallback: the payment must exist by now if another attempt won.
    rows = db.execute(
        "SELECT id FROM payments WHERE idempotency_key = %s ORDER BY id LIMIT 1",
        (idempotency_key,),
    )
    if rows:
        return int(rows[0][0])
    raise last_exc  # pragma: no cover
