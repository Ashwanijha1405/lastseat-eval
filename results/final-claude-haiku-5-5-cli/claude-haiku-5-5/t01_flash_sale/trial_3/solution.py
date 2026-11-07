def purchase(db, product_id: int, qty: int) -> bool:
    db.begin()
    try:
        # The stock check and decrement happen in one statement. In READ COMMITTED,
        # a concurrent purchase waits on the row lock, then re-evaluates
        # `stock >= qty` against the committed value, so stock never goes negative
        # and fitting purchases are never refused just because they overlapped.
        rows = db.execute(
            "UPDATE products SET stock = stock - %s "
            "WHERE id = %s AND stock >= %s "
            "RETURNING id",
            (qty, product_id, qty),
        )
        if not rows:
            # Not enough stock: change nothing and refuse.
            db.rollback()
            return False

        # The decrement and the order row commit together, so every unit that
        # leaves stock is recorded by an order.
        db.execute(
            "INSERT INTO orders (product_id, qty) VALUES (%s, %s)",
            (product_id, qty),
        )
        db.commit()
        return True
    except BaseException:
        db.rollback()
        raise
