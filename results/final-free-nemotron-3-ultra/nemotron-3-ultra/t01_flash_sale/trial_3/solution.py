def purchase(db, product_id: int, qty: int) -> bool:
    sql = """
        WITH updated AS (
            UPDATE products
            SET stock = stock - %(qty)s
            WHERE id = %(product_id)s AND stock >= %(qty)s
            RETURNING id
        )
        INSERT INTO orders (product_id, qty)
        SELECT id, %(qty)s FROM updated
        RETURNING id;
    """
    rows = db.execute(sql, {"product_id": product_id, "qty": qty})
    return bool(rows)


def migrate(db) -> None:
    # No schema changes required for this solution.
    pass
