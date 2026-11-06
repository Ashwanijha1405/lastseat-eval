"""Unique key + select-then-insert, without handling the duplicate.

The constraint prevents a second payment, but the losing attempt's INSERT
fails with UniqueViolation, which reaches the caller as an error instead of
the existing payment's id.

EXPECT: liveness
"""


def migrate(db):
    db.execute("ALTER TABLE payments ADD CONSTRAINT payments_idempotency_key_key UNIQUE (idempotency_key)")


def create_payment(db, idempotency_key, customer_id, amount):
    db.begin()
    rows = db.execute("SELECT id FROM payments WHERE idempotency_key = %s", (idempotency_key,))
    if rows:
        db.commit()
        return rows[0][0]
    [(payment_id,)] = db.execute(
        "INSERT INTO payments (idempotency_key, customer_id, amount) VALUES (%s, %s, %s) RETURNING id",
        (idempotency_key, customer_id, amount),
    )
    db.commit()
    return payment_id
