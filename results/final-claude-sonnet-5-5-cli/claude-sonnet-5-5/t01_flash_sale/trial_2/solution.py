import psycopg.errors


def purchase(db, product_id: int, qty: int) -> bool:
    for _ in range(10):
        try:
            db.begin("read committed")
            rows = db.execute(
                "UPDATE products SET stock = stock - %(q)s "
                "WHERE id = %(p)s AND stock >= %(q)s RETURNING id",
                {"p": product_id, "q": qty},
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
    return False
