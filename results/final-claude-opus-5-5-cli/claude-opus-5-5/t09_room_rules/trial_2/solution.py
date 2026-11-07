from datetime import datetime, timedelta, timezone

import psycopg.errors as pg_errors

_RETRYABLE = (pg_errors.SerializationFailure, pg_errors.DeadlockDetected)
_MAX_ATTEMPTS = 6
_DAILY_LIMIT = 3


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_starts_idx "
        "ON bookings (room_id, starts_at)"
    )


def _day_bounds(starts_at: datetime):
    d = starts_at.astimezone(timezone.utc).date()
    day_start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return day_start, day_start + timedelta(days=1)


def _lock_room(db, room_id: int) -> bool:
    rows = db.execute(
        "SELECT id FROM rooms WHERE id = %s FOR NO KEY UPDATE", (room_id,)
    )
    return bool(rows)


def _check(db, room_id, starts_at, ends_at, exclude_id):
    """Return (overlaps, count_on_day) ignoring booking exclude_id."""
    day_start, day_end = _day_bounds(starts_at)
    rows = db.execute(
        "SELECT "
        "  COUNT(*) FILTER (WHERE starts_at < %(e)s AND ends_at > %(s)s), "
        "  COUNT(*) FILTER (WHERE starts_at >= %(ds)s AND starts_at < %(de)s) "
        "FROM bookings "
        "WHERE room_id = %(r)s AND id <> %(x)s "
        "  AND ((starts_at < %(e)s AND ends_at > %(s)s) "
        "       OR (starts_at >= %(ds)s AND starts_at < %(de)s))",
        {"r": room_id, "s": starts_at, "e": ends_at,
         "ds": day_start, "de": day_end, "x": exclude_id},
    )
    overlaps, count = rows[0]
    return overlaps > 0, count


def _run(db, fn):
    last_exc = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            db.begin("read committed")
            result = fn()
            if result:
                db.commit()
            else:
                db.rollback()
            return result
        except _RETRYABLE as exc:
            last_exc = exc
            try:
                db.rollback()
            except Exception:
                pass
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
    raise last_exc


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    def work():
        if not _lock_room(db, room_id):
            return False
        overlaps, count = _check(db, room_id, starts_at, ends_at, -1)
        if overlaps or count >= _DAILY_LIMIT:
            return False
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) "
            "VALUES (%s, %s, %s)",
            (room_id, starts_at, ends_at),
        )
        return True

    return _run(db, work)


def reschedule(db, booking_id: int, new_starts_at: datetime,
               new_ends_at: datetime) -> bool:
    def work():
        rows = db.execute(
            "SELECT room_id FROM bookings WHERE id = %s", (booking_id,)
        )
        if not rows:
            return False
        room_id = rows[0][0]
        if not _lock_room(db, room_id):
            return False
        # Re-check existence now that the room is locked.
        rows = db.execute(
            "SELECT id FROM bookings WHERE id = %s AND room_id = %s FOR UPDATE",
            (booking_id, room_id),
        )
        if not rows:
            return False
        overlaps, count = _check(db, room_id, new_starts_at, new_ends_at,
                                 booking_id)
        if overlaps or count + 1 > _DAILY_LIMIT:
            return False
        db.execute(
            "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
            (new_starts_at, new_ends_at, booking_id),
        )
        return True

    return _run(db, work)


def cancel(db, booking_id: int) -> bool:
    def work():
        rows = db.execute(
            "SELECT room_id FROM bookings WHERE id = %s", (booking_id,)
        )
        if not rows:
            return False
        room_id = rows[0][0]
        _lock_room(db, room_id)
        rows = db.execute(
            "DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)
        )
        return bool(rows)

    return _run(db, work)
