"""Unique key + ON CONFLICT DO NOTHING RETURNING id, without re-reading.

When the key already exists, DO NOTHING returns no row, so this returns
None instead of the existing payment's id: for a retry alone, and for the
losing attempt of two concurrent ones.

EXPECT: solo, liveness
"""


def migrate(db):
    db.execute("ALTER TABLE payments ADD CONSTRAINT payments_idempotency_key_key UNIQUE (idempotency_key)")


def create_payment(db, idempotency_key, customer_id, amount):
    rows = db.execute(
        "INSERT INTO payments (idempotency_key, customer_id, amount) VALUES (%s, %s, %s)"
        " ON CONFLICT (idempotency_key) DO NOTHING RETURNING id",
        (idempotency_key, customer_id, amount),
    )
    return rows[0][0] if rows else None
