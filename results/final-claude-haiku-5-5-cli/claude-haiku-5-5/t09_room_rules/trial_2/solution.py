import datetime

import psycopg
import psycopg.errors

_UTC = datetime.timezone.utc
_MAX_ATTEMPTS = 5
_RETRYABLE = (
    psycopg.errors.SerializationFailure,
    psycopg.errors.DeadlockDetected,
    psycopg.errors.LockNotAvailable,
)


def _day_bounds(ts):
    """Return [start, end) of the UTC calendar day containing ts."""
    u = ts.astimezone(_UTC)
    start = datetime.datetime(u.year, u.month, u.day, tzinfo=_UTC)
    return start, start + datetime.timedelta(days=1)


def _lock_room(db, room_id):
    # Every change to a room's bookings happens while holding this row lock,
    # so a transaction that holds it sees all earlier committed work for the room.
    db.execute("SELECT id FROM rooms WHERE id = %s FOR UPDATE", (room_id,))


def _lock_booking_room(db, booking_id):
    """Lock the room of an existing booking. Returns room_id, or None if the booking is gone."""
    rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
    if not rows:
        return None
    room_id = rows[0][0]
    _lock_room(db, room_id)
    # Re-read under the lock: the booking may have been cancelled in the meantime.
    rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
    return rows[0][0] if rows else None


def _fits(db, room_id, starts_at, ends_at, exclude_id):
    """Check overlap and the daily limit for a candidate slot. Caller must hold the room lock."""
    clash = db.execute(
        "SELECT 1 FROM bookings "
        "WHERE room_id = %s AND id IS DISTINCT FROM %s "
        "AND starts_at < %s AND ends_at > %s LIMIT 1",
        (room_id, exclude_id, ends_at, starts_at),
    )
    if clash:
        return False

    day_start, day_end = _day_bounds(starts_at)
    count = db.execute(
        "SELECT count(*) FROM bookings "
        "WHERE room_id = %s AND id IS DISTINCT FROM %s "
        "AND starts_at >= %s AND starts_at < %s",
        (room_id, exclude_id, day_start, day_end),
    )[0][0]
    return count < 3


def _with_retries(db, attempt):
    last_error = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            return attempt(db)
        except _RETRYABLE as exc:
            last_error = exc
    raise last_error


def book(db, room_id, starts_at, ends_at):
    def attempt(db):
        db.begin()
        try:
            _lock_room(db, room_id)
            if not _fits(db, room_id, starts_at, ends_at, None):
                db.rollback()
                return False
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                (room_id, starts_at, ends_at),
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise

    return _with_retries(db, attempt)


def reschedule(db, booking_id, new_starts_at, new_ends_at):
    def attempt(db):
        db.begin()
        try:
            room_id = _lock_booking_room(db, booking_id)
            if room_id is None:
                db.rollback()
                return False
            if not _fits(db, room_id, new_starts_at, new_ends_at, booking_id):
                db.rollback()
                return False
            db.execute(
                "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
                (new_starts_at, new_ends_at, booking_id),
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise

    return _with_retries(db, attempt)


def cancel(db, booking_id):
    def attempt(db):
        db.begin()
        try:
            room_id = _lock_booking_room(db, booking_id)
            if room_id is None:
                db.rollback()
                return False
            db.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise

    return _with_retries(db, attempt)
