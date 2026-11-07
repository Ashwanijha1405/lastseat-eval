import psycopg.errors as errors

_RETRYABLE = (
    errors.SerializationFailure,
    errors.DeadlockDetected,
    errors.LockNotAvailable,
)


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS doctors_shift_on_call_idx "
        "ON doctors (shift_id) WHERE on_call"
    )


def go_off_call(db, doctor_id: int) -> bool:
    last_exc = None
    for _ in range(8):
        try:
            db.begin("read committed")
            # Serialize all requests for the same shift by locking the shift row.
            rows = db.execute(
                "SELECT s.id FROM shifts s "
                "JOIN doctors d ON d.shift_id = s.id "
                "WHERE d.id = %s "
                "FOR NO KEY UPDATE OF s",
                (doctor_id,),
            )
            if not rows:
                db.rollback()
                return False
            shift_id = rows[0][0]

            # Fresh snapshot (read committed): sees all previously committed changes.
            others = db.execute(
                "SELECT 1 FROM doctors "
                "WHERE shift_id = %s AND on_call AND id <> %s "
                "LIMIT 1",
                (shift_id, doctor_id),
            )
            if not others:
                db.rollback()
                return False

            db.execute(
                "UPDATE doctors SET on_call = false WHERE id = %s",
                (doctor_id,),
            )
            db.commit()
            return True
        except _RETRYABLE as exc:
            last_exc = exc
            try:
                db.rollback()
            except Exception:
                pass
            continue
    raise last_exc
