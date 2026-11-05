"""Reference: one conditional UPDATE does the check and the decrement together.

The UPDATE locks the product row. A concurrent purchase's UPDATE waits for
that lock; under READ COMMITTED, once the first commits, Postgres re-reads the
newest row version and re-evaluates `stock >= qty` before updating. So the
check always sees the real current stock, and no row comes back when it no
longer fits.
"""


def purchase(db, product_id: int, qty: int) -> bool:
    db.begin()
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
