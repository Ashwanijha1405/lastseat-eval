"""Looks up the key, inserts if missing. No unique constraint.

Both attempts look before either has inserted, both find nothing, and both
insert: the customer is charged twice (safety). The two attempts also return
different ids (1 and 2) for one checkout, which breaks "each attempt returns
the id of the one payment" (liveness).

EXPECT: safety, liveness
"""


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
