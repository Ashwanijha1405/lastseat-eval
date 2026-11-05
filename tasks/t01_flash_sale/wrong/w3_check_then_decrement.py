"""Checks stock with a plain SELECT, then decrements relative to the current value.

`stock = stock - qty` avoids overwriting the other buyer's write, but the
check ran earlier on a value that may be stale. With stock 5, both buyers see
5 >= 3, both decrement, and stock ends at -1. Every unit is still accounted
for by an order, so only the never-negative rule breaks.

EXPECT: safety
"""


def purchase(db, product_id: int, qty: int) -> bool:
    db.begin()
    [(stock,)] = db.execute("SELECT stock FROM products WHERE id = %s", (product_id,))
    if stock < qty:
        db.rollback()
        return False
    db.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (qty, product_id))
    db.execute("INSERT INTO orders (product_id, qty) VALUES (%s, %s)", (product_id, qty))
    db.commit()
    return True
