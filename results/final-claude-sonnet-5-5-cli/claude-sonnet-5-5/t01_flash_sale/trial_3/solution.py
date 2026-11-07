import psycopg.errors


def purchase(db, product_id: int, qty: int) -> bool:
    for _ in range(8):
        try:
            db.begin("read committed")
            # Atomic conditional decrement: the row lock serializes concurrent
            # buyers, and under READ COMMITTED the WHERE clause is re-evaluated
            # against the latest committed row after waiting on the lock.
            rows = db.execute(
                "UPDATE products SET stock = stock - %(q)s "
                "WHERE id = %(p)s AND stock >= %(q)s RETURNING id",
                {"q": qty, "p": product_id},
            )
            if not rows:
                db.rollback()
                return False
            db.execute(
                "INSERT INTO orders (product_id, qty) VALUES (%(p)s, %(q)s)",
                {"p": product_id, "q": qty},
            )
            db.commit()
            return True
        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            db.rollback()
            continue
    return False
