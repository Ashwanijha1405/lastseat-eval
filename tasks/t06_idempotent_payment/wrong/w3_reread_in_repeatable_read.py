"""ON CONFLICT DO NOTHING, then re-read, all inside one REPEATABLE READ transaction.

The snapshot is taken by the INSERT, which may have waited for the other
attempt to commit; the committed payment is not in that snapshot. At
REPEATABLE READ Postgres refuses to skip a conflicting row the snapshot
cannot see and raises SerializationFailure (40001); even without that, the
re-read inside the same snapshot would find nothing.

EXPECT: liveness
"""


def migrate(db):
    db.execute("ALTER TABLE payments ADD CONSTRAINT payments_idempotency_key_key UNIQUE (idempotency_key)")


def create_payment(db, idempotency_key, customer_id, amount):
    db.begin("repeatable read")
    rows = db.execute(
        "INSERT INTO payments (idempotency_key, customer_id, amount) VALUES (%s, %s, %s)"
        " ON CONFLICT (idempotency_key) DO NOTHING RETURNING id",
        (idempotency_key, customer_id, amount),
    )
    if not rows:
        rows = db.execute("SELECT id FROM payments WHERE idempotency_key = %s", (idempotency_key,))
    db.commit()
    return rows[0][0]
