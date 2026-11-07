from psycopg import errors


def purchase(db, product_id: int, qty: int) -> bool:
    for _ in range(25):
        try:
            rows = db.execute(
                """
                WITH updated AS (
                    UPDATE products
                    SET stock = stock - %(qty)s
                    WHERE id = %(product_id)s AND stock >= %(qty)s
                    RETURNING id
                )
                INSERT INTO orders (product_id, qty)
                SELECT id, %(qty)s
                FROM updated
                RETURNING id
                """,
                {"product_id": product_id, "qty": qty},
            )
            return bool(rows)
        except errors.Error:
            try:
                db.rollback()
            except errors.Error:
                pass
            continue
    return False
