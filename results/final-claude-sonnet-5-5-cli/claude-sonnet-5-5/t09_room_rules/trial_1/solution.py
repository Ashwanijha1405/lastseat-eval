from datetime import datetime, timedelta, timezone

import psycopg.errors

_MAX_ATTEMPTS = 3
_RETRYABLE = (
    psycopg.errors.SerializationFailure,
    psycopg.errors.DeadlockDetected,
)


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_start_idx "
        "ON bookings (room_id, starts_at)"
    )


def _day_bounds(ts: datetime):
    u = ts.astimezone(timezone.utc)
    start = u.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _lock_room(db, room_id):
    return db.execute(
        "SELECT id FROM rooms WHERE id = %s FOR NO KEY UPDATE", (room_id,)
    )


def _run(db, fn):
    for _ in range(_MAX_ATTEMPTS):
        try:
            return fn()
        except _RETRYABLE:
            try:
                db.rollback()
            except Exception:
                pass
    return False


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    day_start, day_end = _day_bounds(starts_at)

    def attempt():
        db.begin("read committed")
        if not _lock_room(db, room_id):
            db.rollback()
            return False
        rows = db.execute(
            "SELECT "
            " count(*) FILTER (WHERE starts_at < %(e)s AND ends_at > %(s)s), "
            " count(*) FILTER (WHERE starts_at >= %(ds)s AND starts_at < %(de)s) "
            "FROM bookings WHERE room_id = %(r)s",
            {"e": ends_at, "s": starts_at, "ds": day_start, "de": day_end, "r": room_id},
        )
        overlaps, per_day = rows[0]
        if overlaps > 0 or per_day >= 3:
            db.rollback()
            return False
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
            (room_id, starts_at, ends_at),
        )
        db.commit()
        return True

    return _run(db, attempt)


def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool:
    day_start, day_end = _day_bounds(new_starts_at)

    def attempt():
        # A booking never changes room, so reading room_id before locking is safe.
        pre = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
        if not pre:
            return False
        room_id = pre[0][0]

        db.begin("read committed")
        _lock_room(db, room_id)
        cur = db.execute(
            "SELECT id FROM bookings WHERE id = %s FOR UPDATE", (booking_id,)
        )
        if not cur:
            db.rollback()
            return False
        rows = db.execute(
            "SELECT "
            " count(*) FILTER (WHERE starts_at < %(e)s AND ends_at > %(s)s), "
            " count(*) FILTER (WHERE starts_at >= %(ds)s AND starts_at < %(de)s) "
            "FROM bookings WHERE room_id = %(r)s AND id <> %(b)s",
            {
                "e": new_ends_at, "s": new_starts_at,
                "ds": day_start, "de": day_end,
                "r": room_id, "b": booking_id,
            },
        )
        overlaps, others_on_day = rows[0]
        if overlaps > 0 or others_on_day >= 3:
            db.rollback()
            return False
        db.execute(
            "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
            (new_starts_at, new_ends_at, booking_id),
        )
        db.commit()
        return True

    return _run(db, attempt)


def cancel(db, booking_id: int) -> bool:
    def attempt():
        pre = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
        if not pre:
            return False
        room_id = pre[0][0]

        db.begin("read committed")
        _lock_room(db, room_id)
        deleted = db.execute(
            "DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)
        )
        db.commit()
        return bool(deleted)

    return _run(db, attempt)
