import datetime

import psycopg.errors as errors

_UTC = datetime.timezone.utc
_RETRYABLE = (
    errors.SerializationFailure,
    errors.DeadlockDetected,
    errors.LockNotAvailable,
)
_MAX_ATTEMPTS = 5


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_starts_idx "
        "ON bookings (room_id, starts_at)"
    )


def _day_bounds(ts: datetime.datetime):
    d = ts.astimezone(_UTC).date()
    start = datetime.datetime(d.year, d.month, d.day, tzinfo=_UTC)
    return start, start + datetime.timedelta(days=1)


def _lock_room(db, room_id: int) -> None:
    db.execute(
        "SELECT id FROM rooms WHERE id = %s FOR NO KEY UPDATE",
        (room_id,),
    )


def _fits(db, room_id, starts_at, ends_at, exclude_id) -> bool:
    # Overlap check (half-open intervals), excluding the booking being moved.
    rows = db.execute(
        "SELECT 1 FROM bookings "
        "WHERE room_id = %(r)s AND starts_at < %(e)s AND ends_at > %(s)s "
        "AND id <> %(x)s LIMIT 1",
        {"r": room_id, "s": starts_at, "e": ends_at, "x": exclude_id},
    )
    if rows:
        return False
    day_start, day_end = _day_bounds(starts_at)
    rows = db.execute(
        "SELECT count(*) FROM bookings "
        "WHERE room_id = %(r)s AND starts_at >= %(ds)s AND starts_at < %(de)s "
        "AND id <> %(x)s",
        {"r": room_id, "ds": day_start, "de": day_end, "x": exclude_id},
    )
    return rows[0][0] < 3


def _safe_rollback(db) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def book(db, room_id: int, starts_at: datetime.datetime,
         ends_at: datetime.datetime) -> bool:
    last_exc = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            db.begin("read committed")
            _lock_room(db, room_id)
            if not _fits(db, room_id, starts_at, ends_at, -1):
                db.rollback()
                return False
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) "
                "VALUES (%s, %s, %s)",
                (room_id, starts_at, ends_at),
            )
            db.commit()
            return True
        except _RETRYABLE as exc:
            last_exc = exc
            _safe_rollback(db)
        except Exception:
            _safe_rollback(db)
            raise
    raise last_exc


def reschedule(db, booking_id: int, new_starts_at: datetime.datetime,
               new_ends_at: datetime.datetime) -> bool:
    last_exc = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            db.begin("read committed")
            rows = db.execute(
                "SELECT room_id FROM bookings WHERE id = %s", (booking_id,)
            )
            if not rows:
                db.rollback()
                return False
            room_id = rows[0][0]
            _lock_room(db, room_id)
            # Re-check existence under the room lock (it may have been cancelled).
            rows = db.execute(
                "SELECT id FROM bookings WHERE id = %s FOR UPDATE",
                (booking_id,),
            )
            if not rows:
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
        except _RETRYABLE as exc:
            last_exc = exc
            _safe_rollback(db)
        except Exception:
            _safe_rollback(db)
            raise
    raise last_exc


def cancel(db, booking_id: int) -> bool:
    last_exc = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            rows = db.execute(
                "DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)
            )
            return bool(rows)
        except _RETRYABLE as exc:
            last_exc = exc
    raise last_exc
