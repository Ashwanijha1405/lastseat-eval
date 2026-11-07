import psycopg.errors as errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS doctors_shift_on_call_idx "
        "ON doctors (shift_id) WHERE on_call"
    )


def go_off_call(db, doctor_id: int) -> bool:
    for _ in range(10):
        try:
            db.begin("read committed")
            # Serialize all requests for the same shift by locking the shift row.
            rows = db.execute(
                "SELECT s.id FROM shifts s "
                "JOIN doctors d ON d.shift_id = s.id "
                "WHERE d.id = %(d)s "
                "FOR UPDATE OF s",
                {"d": doctor_id},
            )
            if not rows:
                db.rollback()
                return False
            shift_id = rows[0][0]

            # Fresh snapshot (read committed) taken after acquiring the lock.
            others = db.execute(
                "SELECT count(*) FROM doctors "
                "WHERE shift_id = %(s)s AND on_call AND id <> %(d)s",
                {"s": shift_id, "d": doctor_id},
            )[0][0]

            if others > 0:
                db.execute(
                    "UPDATE doctors SET on_call = false WHERE id = %(d)s",
                    {"d": doctor_id},
                )
                db.commit()
                return True

            db.rollback()
            return False
        except (errors.SerializationFailure, errors.DeadlockDetected,
                errors.LockNotAvailable):
            try:
                db.rollback()
            except Exception:
                pass
            continue
    return False
