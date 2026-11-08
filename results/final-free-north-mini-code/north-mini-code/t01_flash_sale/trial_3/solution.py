
import psycopg
from psycopg import errors
from typing import Optional

def purchase(db, product_id: int, qty: int) -> bool:
    max_attempts = 3
    for _ in range(max_attempts):
        try:
            # Use the strongest isolation to guarantee serializability
            db.begin(isolation="serializable")

            # Lock the product row and read its current stock
            rows = db.execute(
                "SELECT stock FROM products WHERE id = %(pid)s FOR UPDATE",
                {"pid": product_id}
            )
            # The product always exists per the problem statement,
            # but we guard against malformed data just the same.
            if not rows:
                db.rollback()
                return False
            current_stock = rows[0][0]

            if current_stock < qty:
                db.rollback()
                return False

            # Decrease the stock (the row is still locked by the SELECT above)
            db.execute(
                "UPDATE products SET stock = stock - %(qty)s WHERE id = %(pid)s",
                {"qty": qty, "pid": product_id}
            )

            # Record the order
            db.execute(
                "INSERT INTO orders (product_id, qty) VALUES (%(pid)s, %(qty)s)",
                {"pid": product_id, "qty": qty}
            )

            db.commit()
            return True

        except errors.Error:
            # Any database error (deadlock, serialization failure, etc.)
            # forces a rollback and a retry.
            try:
                db.rollback()
            except errors.Error:
                pass
            continue

    # All retry attempts failed
    return False

def migrate(db):
    # No migration required for the given schema
    pass

