from psycopg import errors


def migrate(db) -> None:
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS payments_idempotency_key_idx ON payments (idempotency_key)"
    )


def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    for _ in range(20):
        try:
            rows = db.execute(
                """
                INSERT INTO payments (idempotency_key, customer_id, amount)
                VALUES (%s, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING id
                """,
                (idempotency_key, customer_id, amount),
            )
            if rows:
                return int(rows[0][0])

            rows = db.execute(
                "SELECT id FROM payments WHERE idempotency_key = %s",
                (idempotency_key,),
            )
            if rows:
                return int(rows[0][0])
        except (errors.Error, Exception):
            try:
                db.rollback()
            except Exception:
                pass

    rows = db.execute(
        "SELECT id FROM payments WHERE idempotency_key = %s",
        (idempotency_key,),
    )
    if rows:
        return int(rows[0][0])
    return 0
