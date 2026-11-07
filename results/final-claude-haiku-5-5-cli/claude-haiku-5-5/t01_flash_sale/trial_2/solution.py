import psycopg.errors

MAX_ATTEMPTS = 10


def purchase(db, product_id: int, qty: int) -> bool:
    attempts = 0
    while True:
        attempts += 1
        db.begin()  # default isolation: read committed
        try:
            # Takes the product row lock. If another purchase holds it, this
            # waits, then re-checks stock >= qty on the latest committed version.
            rows = db.execute(
                "UPDATE products SET stock = stock - %s "
                "WHERE id = %s AND stock >= %s "
                "RETURNING id",
                (qty, product_id, qty),
            )
            if not rows:
                # Not enough stock (or no such product): change nothing.
                db.rollback()
                return False

            db.execute(
                "INSERT INTO orders (product_id, qty) VALUES (%s, %s)",
                (product_id, qty),
            )
            db.commit()
            return True
        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            db.rollback()
            if attempts >= MAX_ATTEMPTS:
                raise
            # Retry immediately, no sleep.
