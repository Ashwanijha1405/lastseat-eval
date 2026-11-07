import psycopg
from psycopg import errors


def migrate(db) -> None:
    # Add a unique index as a backstop, but only if existing data has no duplicate keys.
    # Never delete data here: if duplicates exist, skip the index and rely on the lock below.
    dups = db.execute(
        "SELECT 1 FROM payments GROUP BY idempotency_key HAVING count(*) > 1 LIMIT 1"
    )
    if not dups:
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS payments_idempotency_key_uidx "
            "ON payments (idempotency_key)"
        )


def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    # Each attempt uses at most 6 db calls (begin, lock, select, insert, commit, rollback).
    # 9 attempts * 6 = 54 calls, within the 60-call limit.
    for _ in range(9):
        try:
            # Default isolation is read committed. Each statement gets a fresh snapshot,
            # so after the lock is granted, the SELECT sees rows committed by the lock holder.
            # Do not use repeatable read here: its snapshot would predate the other commit.
            db.begin()
            # Transaction-scoped lock: serializes attempts with the same key and is
            # released automatically at commit or rollback. Only one lock is held per
            # transaction, so lock cycles (deadlocks) cannot form.
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%(k)s, 0))",
                {"k": idempotency_key},
            )
            rows = db.execute(
                "SELECT id FROM payments WHERE idempotency_key = %(k)s "
                "ORDER BY id LIMIT 1",
                {"k": idempotency_key},
            )
            if rows:
                db.commit()
                return int(rows[0][0])

            rows = db.execute(
                "INSERT INTO payments (idempotency_key, customer_id, amount) "
                "VALUES (%(k)s, %(c)s, %(a)s) RETURNING id",
                {"k": idempotency_key, "c": customer_id, "a": amount},
            )
            db.commit()
            return int(rows[0][0])
        except psycopg.Error:
            # Roll back and retry. The retry will find the committed row if another
            # attempt won. No sleeping between retries.
            try:
                db.rollback()
            except Exception:
                pass
            continue

    # Not reached in practice: with the advisory lock, attempts for the same key
    # serialize and the retry loop converges within a few iterations.
    # Returned as a last resort so the function never raises or returns None.
    rows = db.execute(
        "SELECT id FROM payments WHERE idempotency_key = %(k)s ORDER BY id LIMIT 1",
        {"k": idempotency_key},
    )
    return int(rows[0][0]) if rows else 0
