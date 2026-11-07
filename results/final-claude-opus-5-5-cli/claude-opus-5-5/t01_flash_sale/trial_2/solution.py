import psycopg.errors as errors

_RETRYABLE = (
    errors.SerializationFailure,
    errors.DeadlockDetected,
    errors.LockNotAvailable,
)

_SQL = """
WITH upd AS (
    UPDATE products
       SET stock = stock - %(qty)s
     WHERE id = %(pid)s
       AND stock >= %(qty)s
    RETURNING id
)
INSERT INTO orders (product_id, qty)
SELECT id, %(qty)s FROM upd
RETURNING id
"""


def purchase(db, product_id: int, qty: int) -> bool:
    params = {"pid": product_id, "qty": qty}
    last_exc = None
    for _ in range(15):
        try:
            db.begin("read committed")
            rows = db.execute(_SQL, params)
            db.commit()
            return len(rows) == 1
        except _RETRYABLE as e:
            last_exc = e
            try:
                db.rollback()
            except Exception:
                pass
            continue
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
    raise last_exc
