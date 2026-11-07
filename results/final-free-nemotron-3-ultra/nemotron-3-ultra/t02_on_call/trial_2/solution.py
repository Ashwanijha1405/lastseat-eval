import psycopg.errors

def go_off_call(db, doctor_id: int) -> bool:
    """
    Attempt to set the given doctor's on_call status to false.
    Returns True if successful (at least one other doctor in the same shift remains on call),
    False otherwise (this doctor is the only one on call in their shift).
    """
    max_attempts = 3
    for _ in range(max_attempts):
        try:
            db.begin()  # default isolation level "read committed"
            # Lock the shift row to serialize all go_off_call operations for this shift.
            rows = db.execute(
                "SELECT s.id FROM shifts s JOIN doctors d ON d.shift_id = s.id WHERE d.id = %s FOR UPDATE",
                (doctor_id,)
            )
            if not rows:
                # Should not happen per problem statement (doctor always exists).
                db.rollback()
                return False
            shift_id = rows[0][0]

            # Count how many doctors in this shift are currently on call.
            rows = db.execute(
                "SELECT count(*) FROM doctors WHERE shift_id = %s AND on_call = true",
                (shift_id,)
            )
            on_call_count = rows[0][0]

            if on_call_count > 1:
                # At least one other doctor is on call -> we can go off call.
                db.execute(
                    "UPDATE doctors SET on_call = false WHERE id = %s",
                    (doctor_id,)
                )
                db.commit()
                return True
            else:
                # This doctor is the only one on call; cannot go off call.
                db.commit()
                return False

        except psycopg.errors.DeadlockDetected:
            db.rollback()
            # Retry on deadlock (very unlikely with our locking order).
            continue
        except Exception:
            db.rollback()
            raise

    # If we exhausted retries (should not happen in practice), treat as failure.
    return False
