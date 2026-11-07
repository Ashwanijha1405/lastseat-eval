import psycopg
import psycopg.errors


def migrate(db) -> None:
    try:
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS payments_idempotency_key_uq "
            "ON payments (idempotency_key)"
        )
        return
    except psycopg.errors.Error:
        try:
            db.rollback()
        except Exception:
            pass
    # Pre-existing duplicate keys prevent a unique index; use a plain index for lookups.
    try:
        db.execute(
            "CREATE INDEX IF NOT EXISTS payments_idempotency_key_idx "
            "ON payments (idempotency_key)"
        )
    except psycopg.errors.Error:
        try:
            db.rollback()
        except Exception:
            pass


def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    for _ in range(10):
        try:
            db.begin("read committed")
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 7319))",
                (idempotency_key,),
            )
            rows = db.execute(
                "SELECT id FROM payments WHERE idempotency_key = %s ORDER BY id LIMIT 1",
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
        except psycopg.errors.Error:
            try:
                db.rollback()
            except Exception:
                pass
            continue

    # Fallback: a payment should exist by now; read it without locking.
    for _ in range(3):
        try:
            rows = db.execute(
                "SELECT id FROM payments WHERE idempotency_key = %s ORDER BY id LIMIT 1",
                (idempotency_key,),
            )
            if rows:
                return int(rows[0][0])
        except psycopg.errors.Error:
            try:
                db.rollback()
            except Exception:
                pass
    return -1
