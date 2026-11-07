def purchase(db, product_id: int, qty: int) -> bool:
    sql = """
    WITH updated AS (
        UPDATE products
        SET stock = stock - %(qty)s
        WHERE id = %(product_id)s AND stock >= %(qty)s
        RETURNING id
    )
    INSERT INTO orders (product_id, qty)
    SELECT %(product_id)s, %(qty)s FROM updated
    RETURNING id;
    """
    result = db.execute(sql, {"product_id": product_id, "qty": qty})
    return bool(result)
