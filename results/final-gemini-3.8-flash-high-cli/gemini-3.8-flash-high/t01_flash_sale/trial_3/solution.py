from psycopg import errors


def migrate(db) -> None:
    pass


def purchase(db, product_id: int, qty: int) -> bool:
    for _ in range(15):
        try:
            db.begin(isolation="read committed")
            rows = db.execute(
                """
                WITH updated AS (
                    UPDATE products
                    SET stock = stock - %(qty)s
                    WHERE id = %(product_id)s AND stock >= %(qty)s
                    RETURNING id
                )
                INSERT INTO orders (product_id, qty)
                SELECT updated.id, %(qty)s
                FROM updated
                RETURNING orders.id
                """,
                {"product_id": product_id, "qty": qty},
            )
            if rows:
                db.commit()
                return True
            else:
                db.rollback()
                return False
        except (errors.TransactionRollbackError, errors.OperationalError):
            try:
                db.rollback()
            except Exception:
                pass
            continue
    return False
