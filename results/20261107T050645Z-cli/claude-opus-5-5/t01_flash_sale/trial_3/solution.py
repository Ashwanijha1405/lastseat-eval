import psycopg.errors


def purchase(db, product_id: int, qty: int) -> bool:
    for _ in range(10):
        try:
            db.begin("read committed")
            rows = db.execute(
                "UPDATE products SET stock = stock - %(qty)s "
                "WHERE id = %(pid)s AND stock >= %(qty)s "
                "RETURNING stock",
                {"pid": product_id, "qty": qty},
            )
            if not rows:
                db.rollback()
                return False
            db.execute(
                "INSERT INTO orders (product_id, qty) VALUES (%(pid)s, %(qty)s)",
                {"pid": product_id, "qty": qty},
            )
            db.commit()
            return True
        except (
            psycopg.errors.SerializationFailure,
            psycopg.errors.DeadlockDetected,
            psycopg.errors.LockNotAvailable,
        ):
            try:
                db.rollback()
            except Exception:
                pass
            continue
    return False
