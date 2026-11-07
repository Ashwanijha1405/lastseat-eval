from datetime import datetime, timedelta, timezone
from psycopg import errors

_RETRYABLE = (errors.SerializationFailure, errors.DeadlockDetected, errors.LockNotAvailable)
_MAX_TRIES = 5


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_starts_idx "
        "ON bookings (room_id, starts_at)"
    )


def _day_bounds(starts_at: datetime):
    d = starts_at.astimezone(timezone.utc).date()
    lo = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return lo, lo + timedelta(days=1)


def _lock_room(db, room_id):
    db.execute("SELECT id FROM rooms WHERE id = %s FOR UPDATE", (room_id,))


def _fits(db, room_id, starts_at, ends_at, exclude_id):
    # Overlap check against other bookings of the room.
    rows = db.execute(
        "SELECT 1 FROM bookings "
        "WHERE room_id = %s AND id <> %s AND starts_at < %s AND ends_at > %s "
        "LIMIT 1",
        (room_id, exclude_id, ends_at, starts_at),
    )
    if rows:
        return False
    lo, hi = _day_bounds(starts_at)
    rows = db.execute(
        "SELECT count(*) FROM bookings "
        "WHERE room_id = %s AND id <> %s AND starts_at >= %s AND starts_at < %s",
        (room_id, exclude_id, lo, hi),
    )
    return rows[0][0] < 3


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    for _ in range(_MAX_TRIES):
        try:
            db.begin("read committed")
            _lock_room(db, room_id)
            if not _fits(db, room_id, starts_at, ends_at, -1):
                db.rollback()
                return False
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                (room_id, starts_at, ends_at),
            )
            db.commit()
            return True
        except _RETRYABLE:
            db.rollback()
    return False


def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool:
    for _ in range(_MAX_TRIES):
        try:
            db.begin("read committed")
            rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
            if not rows:
                db.rollback()
                return False
            room_id = rows[0][0]
            _lock_room(db, room_id)
            # Re-check existence under the room lock (it may have been cancelled).
            rows = db.execute(
                "SELECT id FROM bookings WHERE id = %s FOR UPDATE", (booking_id,)
            )
            if not rows:
                db.rollback()
                return False
            if not _fits(db, room_id, new_starts_at, new_ends_at, booking_id):
                db.rollback()
                return False
            rows = db.execute(
                "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s RETURNING id",
                (new_starts_at, new_ends_at, booking_id),
            )
            if not rows:
                db.rollback()
                return False
            db.commit()
            return True
        except _RETRYABLE:
            db.rollback()
    return False


def cancel(db, booking_id: int) -> bool:
    for _ in range(_MAX_TRIES):
        try:
            rows = db.execute(
                "DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)
            )
            return bool(rows)
        except _RETRYABLE:
            pass
    return False
