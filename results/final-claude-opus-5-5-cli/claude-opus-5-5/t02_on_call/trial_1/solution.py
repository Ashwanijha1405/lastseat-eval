import psycopg.errors as errors


def go_off_call(db, doctor_id: int) -> bool:
    last_exc = None
    for _ in range(5):
        try:
            db.begin("read committed")
            # Lock this doctor's shift row; serializes all requests within the same shift.
            rows = db.execute(
                "SELECT s.id FROM shifts s JOIN doctors d ON d.shift_id = s.id "
                "WHERE d.id = %s FOR UPDATE OF s",
                (doctor_id,),
            )
            if not rows:
                db.rollback()
                return False
            shift_id = rows[0][0]
            # Fresh snapshot (read committed) taken after the lock was acquired.
            others = db.execute(
                "SELECT count(*) FROM doctors "
                "WHERE shift_id = %s AND on_call AND id <> %s",
                (shift_id, doctor_id),
            )[0][0]
            if others > 0:
                db.execute(
                    "UPDATE doctors SET on_call = false WHERE id = %s",
                    (doctor_id,),
                )
                db.commit()
                return True
            db.rollback()
            return False
        except (errors.SerializationFailure, errors.DeadlockDetected,
                errors.LockNotAvailable) as e:
            last_exc = e
            try:
                db.rollback()
            except Exception:
                pass
    raise last_exc
