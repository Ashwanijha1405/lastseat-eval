import psycopg.errors

def go_off_call(db, doctor_id: int) -> bool:
    """
    Attempt to set the given doctor off call.
    Returns True if successful (at least one other doctor in the same shift remains on call),
    False otherwise (this doctor is the only one on call in their shift).
    """
    sql = """
    WITH locked AS (
        SELECT id
        FROM doctors
        WHERE shift_id = (SELECT shift_id FROM doctors WHERE id = %(doctor_id)s)
          AND on_call = true
        ORDER BY id
        FOR UPDATE
    ),
    cnt AS (
        SELECT count(*) AS c FROM locked
    )
    UPDATE doctors
    SET on_call = false
    WHERE id = %(doctor_id)s
      AND on_call = true
      AND (SELECT c FROM cnt) > 1
    RETURNING 1
    """
    max_attempts = 5
    for _ in range(max_attempts):
        db.begin()
        try:
            rows = db.execute(sql, {"doctor_id": doctor_id})
            db.commit()
            return len(rows) > 0
        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise
    # With proper lock ordering this should never be reached.
    raise RuntimeError("Failed to go off call after multiple retries")


def migrate(db) -> None:
    # No schema changes required for the base tables.
    pass
