import psycopg.errors as errors


def migrate(db) -> None:
    # Speeds up the overlap check. No exclusion constraint, because the
    # existing data might not satisfy it and the migration would fail.
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_time_idx "
        "ON bookings (room_id, starts_at, ends_at)"
    )


def book_room(db, room_id, starts_at, ends_at) -> bool:
    params = {"room": room_id, "s": starts_at, "e": ends_at}
    for _ in range(10):
        try:
            db.begin("read committed")
            # Lock the room row so requests for the same room run one at a time.
            db.execute(
                "SELECT id FROM rooms WHERE id = %(room)s FOR UPDATE",
                params,
            )
            # In READ COMMITTED each statement takes a fresh snapshot, so this
            # sees every booking committed by whoever held the lock before us.
            rows = db.execute(
                "SELECT 1 FROM bookings "
                "WHERE room_id = %(room)s "
                "AND starts_at < %(e)s AND ends_at > %(s)s "
                "LIMIT 1",
                params,
            )
            if rows:
                db.rollback()
                return False
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) "
                "VALUES (%(room)s, %(s)s, %(e)s)",
                params,
            )
            db.commit()
            return True
        except (
            errors.SerializationFailure,
            errors.DeadlockDetected,
            errors.LockNotAvailable,
        ):
            try:
                db.rollback()
            except Exception:
                pass
            continue
    return False
