"""Reference: unique key + INSERT ... ON CONFLICT DO NOTHING, then re-read.

The unique index sees other transactions' uncommitted rows, so a concurrent
attempt's INSERT waits for the first one. If the first commits, ON CONFLICT
DO NOTHING inserts nothing and returns no row (no error, but no id either).
The id is then read by a new READ COMMITTED statement, whose fresh snapshot
includes the committed payment.
"""


def migrate(db) -> None:
    db.execute("ALTER TABLE payments ADD CONSTRAINT payments_idempotency_key_key UNIQUE (idempotency_key)")


def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int:
    rows = db.execute(
        "INSERT INTO payments (idempotency_key, customer_id, amount) VALUES (%s, %s, %s)"
        " ON CONFLICT (idempotency_key) DO NOTHING RETURNING id",
        (idempotency_key, customer_id, amount),
    )
    if rows:
        return rows[0][0]
    [(payment_id,)] = db.execute("SELECT id FROM payments WHERE idempotency_key = %s", (idempotency_key,))
    return payment_id
