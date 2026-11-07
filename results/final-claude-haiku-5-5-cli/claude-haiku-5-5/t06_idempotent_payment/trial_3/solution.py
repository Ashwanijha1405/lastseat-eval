import psycopg
from psycopg import errors


def migrate(db) -> None:
    # Enforces rule 1 at the database level, so no two rows can share a key.
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS payments_idempotency_key_uidx "
        "ON payments (idempotency_key)"
    )


def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    last_error = None
    # Bounded retries: at most 6 attempts, each using at most 4 db calls
    # (begin, insert, select, commit), plus one rollback per failure,
    # which stays well under the 60-call limit.
    for _ in range(6):
        try:
            db.begin()  # default isolation: read committed
            rows = db.execute(
                "INSERT INTO payments (idempotency_key, customer_id, amount) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (idempotency_key) DO NOTHING "
                "RETURNING id",
                (idempotency_key, customer_id, amount),
            )
            if not rows:
                # A row with this key already exists. Under read committed,
                # this statement takes a fresh snapshot, so it sees the
                # committed row from the concurrent attempt.
                rows = db.execute(
                    "SELECT id FROM payments WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
            db.commit()
            if rows:
                return int(rows[0][0])
            # Not expected: the conflicting row vanished before we read it.
            # Retry the whole attempt.
        except (
            errors.SerializationFailure,
            errors.DeadlockDetected,
            errors.LockNotAvailable,
            errors.UniqueViolation,
        ) as exc:
            last_error = exc
            db.rollback()
    # Every attempt failed on a transient error. Propagate the error rather
    # than return None, since the function must return an int.
    raise last_error
