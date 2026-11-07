from datetime import datetime, timedelta, timezone

from psycopg import errors

MAX_PER_DAY = 3
MAX_ATTEMPTS = 6
_RETRYABLE = (errors.SerializationFailure, errors.DeadlockDetected)


def _day_bounds(ts: datetime):
    utc = ts.astimezone(timezone.utc)
    day_start = datetime(utc.year, utc.month, utc.day, tzinfo=timezone.utc)
    return day_start, day_start + timedelta(days=1)


def _lock_room(db, room_id):
    # Serializes every write to this room's bookings. Waits (no NOWAIT),
    # so concurrent requests are queued rather than refused.
    db.execute("SELECT id FROM rooms WHERE id = %s FOR UPDATE", (room_id,))


def _overlaps(db, room_id, starts_at, ends_at, exclude_id):
    rows = db.execute(
        "SELECT 1 FROM bookings "
        "WHERE room_id = %(room)s "
        "  AND starts_at < %(end)s "
        "  AND ends_at > %(start)s "
        "  AND id IS DISTINCT FROM %(excl)s::int "
        "LIMIT 1",
        {"room": room_id, "start": starts_at, "end": ends_at, "excl": exclude_id},
    )
    return bool(rows)


def _count_on_day(db, room_id, ts, exclude_id):
    day_start, day_end = _day_bounds(ts)
    rows = db.execute(
        "SELECT count(*) FROM bookings "
        "WHERE room_id = %(room)s "
        "  AND starts_at >= %(ds)s "
        "  AND starts_at < %(de)s "
        "  AND id IS DISTINCT FROM %(excl)s::int",
        {"room": room_id, "ds": day_start, "de": day_end, "excl": exclude_id},
    )
    return rows[0][0]


def _run(db, body):
    for _ in range(MAX_ATTEMPTS):
        db.begin()
        try:
            result = body(db)
            if result:
                db.commit()
            else:
                db.rollback()
            return result
        except _RETRYABLE:
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise
    return False


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    def body(db):
        _lock_room(db, room_id)
        if _overlaps(db, room_id, starts_at, ends_at, None):
            return False
        if _count_on_day(db, room_id, starts_at, None) >= MAX_PER_DAY:
            return False
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
            (room_id, starts_at, ends_at),
        )
        return True

    return _run(db, body)


def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool:
    def body(db):
        rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
        if not rows:
            return False
        room_id = rows[0][0]  # a booking never changes rooms
        _lock_room(db, room_id)
        # Re-check under the lock: it may have been cancelled meanwhile.
        if not db.execute("SELECT 1 FROM bookings WHERE id = %s", (booking_id,)):
            return False
        if _overlaps(db, room_id, new_starts_at, new_ends_at, booking_id):
            return False
        if _count_on_day(db, room_id, new_starts_at, booking_id) >= MAX_PER_DAY:
            return False
        db.execute(
            "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
            (new_starts_at, new_ends_at, booking_id),
        )
        return True

    return _run(db, body)


def cancel(db, booking_id: int) -> bool:
    def body(db):
        rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
        if not rows:
            return False
        _lock_room(db, rows[0][0])
        deleted = db.execute(
            "DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)
        )
        return bool(deleted)

    return _run(db, body)
