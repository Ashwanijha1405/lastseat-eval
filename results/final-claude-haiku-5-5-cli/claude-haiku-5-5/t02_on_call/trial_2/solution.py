import psycopg.errors


def _attempt(db, doctor_id: int) -> bool:
    db.begin()  # default isolation: read committed
    try:
        rows = db.execute(
            "SELECT shift_id FROM doctors WHERE id = %s",
            (doctor_id,),
        )
        if not rows:
            db.commit()
            return False
        shift_id = rows[0][0]

        # Serialise all go-off-call requests for this shift. shift_id never changes,
        # so the lock order (shift first, then doctor rows) is the same for everyone.
        db.execute(
            "SELECT id FROM shifts WHERE id = %s FOR UPDATE",
            (shift_id,),
        )

        # Read committed: this statement's snapshot is taken after the lock is held,
        # so it sees every earlier committed change in this shift.
        others = db.execute(
            "SELECT count(*) FROM doctors "
            "WHERE shift_id = %s AND id <> %s AND on_call",
            (shift_id, doctor_id),
        )[0][0]

        if others == 0:
            db.commit()  # nothing changed; the commit just releases the lock
            return False

        db.execute(
            "UPDATE doctors SET on_call = false WHERE id = %s AND on_call",
            (doctor_id,),
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def go_off_call(db, doctor_id: int) -> bool:
    # Bounded retries. With the shift lock these errors should not occur,
    # but they are retried if they do. Each attempt uses at most 6 db calls.
    last_error = None
    for _ in range(5):
        try:
            return _attempt(db, doctor_id)
        except (
            psycopg.errors.SerializationFailure,
            psycopg.errors.DeadlockDetected,
            psycopg.errors.LockNotAvailable,
        ) as exc:
            last_error = exc
            continue
    raise last_error
