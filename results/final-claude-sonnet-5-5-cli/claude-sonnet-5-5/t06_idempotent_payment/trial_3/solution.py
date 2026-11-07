import psycopg.errors


def migrate(db) -> None:
    # Backstop: enforce uniqueness at the database level. If pre-existing data
    # already contains duplicates, the index can't be built; the advisory-lock
    # logic in create_payment still guarantees no new duplicates.
    try:
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS payments_idempotency_key_uq "
            "ON payments (idempotency_key)"
        )
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    last_err = None
    for _ in range(10):
        try:
            db.begin("read committed")
            # Serialize all attempts with the same key. The lock is released at
            # commit/rollback; each later statement takes a fresh snapshot in
            # READ COMMITTED, so it sees the winner's committed row.
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (idempotency_key,),
            )
            rows = db.execute(
                "SELECT id FROM payments WHERE idempotency_key = %s ORDER BY id LIMIT 1",
                (idempotency_key,),
            )
            if rows:
                pid = rows[0][0]
            else:
                rows = db.execute(
                    "INSERT INTO payments (idempotency_key, customer_id, amount) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (idempotency_key, customer_id, amount),
                )
                pid = rows[0][0]
            db.commit()
            return int(pid)
        except (
            psycopg.errors.UniqueViolation,
            psycopg.errors.SerializationFailure,
            psycopg.errors.DeadlockDetected,
        ) as e:
            last_err = e
            try:
                db.rollback()
            except Exception:
                pass
    # Final fallback: the row must exist by now if a unique violation occurred.
    rows = db.execute(
        "SELECT id FROM payments WHERE idempotency_key = %s ORDER BY id LIMIT 1",
        (idempotency_key,),
    )
    return int(rows[0][0])
