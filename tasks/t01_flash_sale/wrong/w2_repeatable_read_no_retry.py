"""The reference's conditional UPDATE, but under REPEATABLE READ with no retry.

REPEATABLE READ keeps the snapshot from the transaction's first statement.
If the other buyer commits a change to the same row after that snapshot, the
UPDATE cannot re-check against the newer version and fails with
SerializationFailure (40001). Nothing is oversold, but in "both fit" one
buyer gets an error instead of their order.

EXPECT: liveness
"""


def purchase(db, product_id: int, qty: int) -> bool:
    db.begin("repeatable read")
    rows = db.execute(
        "UPDATE products SET stock = stock - %(qty)s"
        " WHERE id = %(id)s AND stock >= %(qty)s RETURNING stock",
        {"id": product_id, "qty": qty},
    )
    if not rows:
        db.rollback()
        return False
    db.execute("INSERT INTO orders (product_id, qty) VALUES (%s, %s)", (product_id, qty))
    db.commit()
    return True
