"""Reads stock, computes the new value in Python, writes it back.

Both buyers can read stock=5 before either writes. Both see 5 >= 3, both write
stock=2 and both insert an order: 6 units ordered but only 3 left stock. The
second write overwrites the first (a lost update), so conservation breaks.
Both buyers still get True, so liveness is not what fails.

EXPECT: safety
"""


def purchase(db, product_id: int, qty: int) -> bool:
    db.begin()
    [(stock,)] = db.execute("SELECT stock FROM products WHERE id = %s", (product_id,))
    if stock < qty:
        db.rollback()
        return False
    db.execute("UPDATE products SET stock = %s WHERE id = %s", (stock - qty, product_id))
    db.execute("INSERT INTO orders (product_id, qty) VALUES (%s, %s)", (product_id, qty))
    db.commit()
    return True
