def purchase(db, product_id: int, qty: int) -> bool:
    rows = db.execute(
        """
        WITH upd AS (
            UPDATE products
               SET stock = stock - %(qty)s
             WHERE id = %(product_id)s
               AND stock >= %(qty)s
         RETURNING id
        )
        INSERT INTO orders (product_id, qty)
        SELECT id, %(qty)s FROM upd
        RETURNING id
        """,
        {"product_id": product_id, "qty": qty},
    )
    return len(rows) == 1
