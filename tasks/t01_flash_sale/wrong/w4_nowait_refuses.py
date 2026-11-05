"""Locks the row with FOR UPDATE NOWAIT and refuses if someone else holds it.

Never oversells: whoever holds the lock decides alone. But a buyer who
arrives while another purchase is in progress gets False immediately, even
when there is plenty of stock for both. In "both fit" that is a refused
valid purchase.

EXPECT: liveness
"""

from psycopg import errors


def purchase(db, product_id: int, qty: int) -> bool:
    db.begin()
    try:
        [(stock,)] = db.execute("SELECT stock FROM products WHERE id = %s FOR UPDATE NOWAIT", (product_id,))
    except errors.LockNotAvailable:
        db.rollback()
        return False
    if stock < qty:
        db.rollback()
        return False
    db.execute("UPDATE products SET stock = %s WHERE id = %s", (stock - qty, product_id))
    db.execute("INSERT INTO orders (product_id, qty) VALUES (%s, %s)", (product_id, qty))
    db.commit()
    return True
