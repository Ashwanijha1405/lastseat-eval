import psycopg.errors

def go_off_call(db, doctor_id: int) -> bool:
    # Number of attempts to avoid infinite loops (max 60 db calls per request)
    MAX_ATTEMPTS = 5

    for _ in range(MAX_ATTEMPTS):
        try:
            # Start a serializable transaction to avoid write‑skew
            db.begin(isolation="serializable")

            # Fetch the doctor's shift and on_call status
            doctor_rows = db.execute(
                "SELECT shift_id, on_call FROM doctors WHERE id = %s",
                (doctor_id,)
            )
            if not doctor_rows:
                # Doctor not found – should not happen, abort this attempt
                db.rollback()
                continue

            shift_id, on_call = doctor_rows[0]

            # If the doctor is already off‑call, refuse the request
            if not on_call:
                return False

            # Count how many doctors in the same shift are on call
            count_rows = db.execute(
                "SELECT COUNT(*) FROM doctors WHERE shift_id = %s AND on_call = true",
                (shift_id,)
            )
            on_call_count = count_rows[0][0]

            # If this doctor is the only one on call, refuse
            if on_call_count <= 1:
                return False

            # Atomically turn off this doctor only if still on call
            update_res = db.execute(
                "UPDATE doctors SET on_call = false "
                "WHERE id = %s AND on_call = true RETURNING id",
                (doctor_id,)
            )

            if update_res:
                # Successfully turned off – commit the transaction
                db.commit()
                return True
            else:
                # The row was already changed by another concurrent request
                db.rollback()
                continue

        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            # Serialization or deadlock – rollback and retry
            db.rollback()
            continue

    # If we exhausted attempts, raise an error (should not happen in tests)
    raise RuntimeError("go_off_call failed after retries")
