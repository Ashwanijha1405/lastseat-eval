import psycopg.errors

def go_off_call(db, doctor_id: int) -> bool:
    """
    Attempt to set the given doctor's on_call status to false.
    Returns True if successful (at least one other doctor in the same shift remains on call),
    False otherwise (doctor is the only one on call, or not on call anymore).
    """
    max_retries = 5
    for _ in range(max_retries):
        try:
            db.begin()  # default isolation level: read committed

            # Lock all on‑call doctors in the same shift in a consistent order (by id)
            rows = db.execute(
                """
                SELECT id FROM doctors
                WHERE shift_id = (SELECT shift_id FROM doctors WHERE id = %(doctor_id)s)
                  AND on_call = true
                ORDER BY id
                FOR UPDATE
                """,
                {"doctor_id": doctor_id}
            )

            locked_ids = {row[0] for row in rows}

            # If the doctor is no longer on call (e.g. another request for the same doctor
            # already succeeded), we cannot go off call.
            if doctor_id not in locked_ids:
                db.commit()
                return False

            on_call_count = len(rows)
            if on_call_count >= 2:
                # At least one other doctor is on call – we can go off call.
                db.execute(
                    "UPDATE doctors SET on_call = false WHERE id = %(doctor_id)s",
                    {"doctor_id": doctor_id}
                )
                db.commit()
                return True
            else:
                # This doctor is the only one on call in the shift.
                db.commit()
                return False

        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            # Transient concurrency error – roll back and retry.
            db.rollback()
            continue
        except Exception:
            # Any other error – roll back and treat as failure (do not raise).
            db.rollback()
            return False

    # Retries exhausted (should not happen under normal contention).
    return False
