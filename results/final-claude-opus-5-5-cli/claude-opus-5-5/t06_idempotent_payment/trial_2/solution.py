import psycopg.errors as errors


def migrate(db) -> None:
    try:
        db.begin()
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS payments_idempotency_key_uniq "
            "ON payments (idempotency_key)"
        )
        db.commit()
        return
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    # Existing duplicates prevent a unique index; fall back to a plain index.
    db.begin()
    db.execute(
        "CREATE INDEX IF NOT EXISTS payments_idempotency_key_idx "
        "ON payments (idempotency_key)"
    )
    db.commit()


def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    last_exc = None
    for _ in range(8):
        try:
            db.begin("read committed")
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
    # Final fallback: return the existing row if one is present.
    rows = db.execute(
        "SELECT id FROM payments WHERE idempotency_key = %s ORDER BY id LIMIT 1",
        (idempotency_key,),
    )
    if rows:
        return int(rows[0][0])
    raise last_exc  # unreachable in practice
