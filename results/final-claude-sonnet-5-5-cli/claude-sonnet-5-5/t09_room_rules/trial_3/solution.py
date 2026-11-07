from datetime import datetime, timedelta, timezone
import psycopg.errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_starts_idx "
        "ON bookings (room_id, starts_at)"
    )


def _day_bounds(ts):
    u = ts.astimezone(timezone.utc)
    d0 = u.replace(hour=0, minute=0, second=0, microsecond=0)
    return d0, d0 + timedelta(days=1)


def _lock_room(db, room_id):
    # Serialize all writers of one room. NO KEY UPDATE doesn't conflict
    # with the FK key-share locks taken by inserts.
    return db.execute(
        "SELECT id FROM rooms WHERE id = %s FOR NO KEY UPDATE", (room_id,)
    )


def book(db, room_id, starts_at, ends_at):
    d0, d1 = _day_bounds(starts_at)
    for _ in range(5):
        try:
            db.begin("read committed")
            if not _lock_room(db, room_id):
                db.rollback()
                return False
            rows = db.execute(
                "SELECT count(*) FILTER (WHERE starts_at < %s AND ends_at > %s), "
                "       count(*) FILTER (WHERE starts_at >= %s AND starts_at < %s) "
                "FROM bookings WHERE room_id = %s",
                (ends_at, starts_at, d0, d1, room_id),
            )
            overlaps, per_day = rows[0]
            if overlaps > 0 or per_day >= 3:
                db.rollback()
                return False
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) "
                "VALUES (%s, %s, %s)",
                (room_id, starts_at, ends_at),
            )
            db.commit()
            return True
        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            db.rollback()
    return False


def reschedule(db, booking_id, new_starts_at, new_ends_at):
    d0, d1 = _day_bounds(new_starts_at)
    for _ in range(5):
        try:
            r = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
            if not r:
                return False
            room_id = r[0][0]
            db.begin("read committed")
            _lock_room(db, room_id)
            # Re-check existence under the room lock (may have been cancelled).
            if not db.execute(
                "SELECT id FROM bookings WHERE id = %s FOR UPDATE", (booking_id,)
            ):
                db.rollback()
                return False
            rows = db.execute(
                "SELECT count(*) FILTER (WHERE starts_at < %s AND ends_at > %s), "
                "       count(*) FILTER (WHERE starts_at >= %s AND starts_at < %s) "
                "FROM bookings WHERE room_id = %s AND id <> %s",
                (new_ends_at, new_starts_at, d0, d1, room_id, booking_id),
            )
            overlaps, per_day = rows[0]
            if overlaps > 0 or per_day + 1 > 3:
                db.rollback()
                return False
            db.execute(
                "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
                (new_starts_at, new_ends_at, booking_id),
            )
            db.commit()
            return True
        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            db.rollback()
    return False


def cancel(db, booking_id):
    rows = db.execute(
        "DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)
    )
    return bool(rows)
