from datetime import date, datetime, timedelta, timezone

from psycopg import errors as pg_errors

_MAX_ATTEMPTS = 5
_MAX_PER_DAY = 3
_EPOCH = date(1970, 1, 1)
_RETRYABLE = (pg_errors.DeadlockDetected, pg_errors.SerializationFailure)


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_starts_at_idx "
        "ON bookings (room_id, starts_at)"
    )


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    return _transact(db, lambda conn: _book(conn, room_id, starts_at, ends_at))


def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool:
    return _transact(
        db, lambda conn: _reschedule(conn, booking_id, new_starts_at, new_ends_at)
    )


def cancel(db, booking_id: int) -> bool:
    return _transact(db, lambda conn: _cancel(conn, booking_id))


# ---------------------------------------------------------------------------
# Transaction wrapper: bounded retry on deadlock / serialization failure.
# The body returns (should_commit, result).
# ---------------------------------------------------------------------------

def _transact(db, body):
    last_error = None
    for _ in range(_MAX_ATTEMPTS):
        db.begin("read committed")
        try:
            should_commit, result = body(db)
            if should_commit:
                db.commit()
            else:
                db.rollback()
            return result
        except _RETRYABLE as exc:
            last_error = exc
            db.rollback()
        except BaseException:
            db.rollback()
            raise
    raise last_error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_day(ts: datetime) -> date:
    return ts.astimezone(timezone.utc).date()


def _day_bounds(day: date):
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _day_key(day: date) -> int:
    return (day - _EPOCH).days


def _lock_days(db, room_id: int, days) -> None:
    # Locks are taken in sorted order so that two requests never hold
    # one day while waiting for another in the opposite order.
    # Locks are per (room, UTC day): requests on other rooms or other
    # days never wait for each other.
    for day in sorted(set(days)):
        db.execute(
            "SELECT pg_advisory_xact_lock(%s::int4, %s::int4)",
            (room_id, _day_key(day)),
        )


def _room_day_state(db, room_id: int, day: date, exclude_id):
    """Return (number of other bookings on that day, whether any overlaps
    the window). Callers must hold the (room, day) lock."""
    day_start, day_end = _day_bounds(day)
    return None  # replaced below


def _room_day_state(db, room_id: int, day: date, starts_at: datetime,
                    ends_at: datetime, exclude_id):
    day_start, day_end = _day_bounds(day)
    rows = db.execute(
        """
        SELECT count(*),
               coalesce(bool_or(starts_at < %(ends)s AND ends_at > %(starts)s), false)
        FROM bookings
        WHERE room_id = %(room)s
          AND starts_at >= %(day_start)s
          AND starts_at <  %(day_end)s
          AND id IS DISTINCT FROM %(exclude)s::int
        """,
        {
            "room": room_id,
            "starts": starts_at,
            "ends": ends_at,
            "day_start": day_start,
            "day_end": day_end,
            "exclude": exclude_id,
        },
    )
    count, overlaps = rows[0]
    return int(count), bool(overlaps)


# ---------------------------------------------------------------------------
# Bodies. Each returns (should_commit, result).
# ---------------------------------------------------------------------------

def _book(db, room_id, starts_at, ends_at):
    day = _utc_day(starts_at)
    _lock_days(db, room_id, [day])
    count, overlaps = _room_day_state(db, room_id, day, starts_at, ends_at, None)
    if overlaps or count >= _MAX_PER_DAY:
        return False, False
    db.execute(
        "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
        (room_id, starts_at, ends_at),
    )
    return True, True


def _reschedule(db, booking_id, new_starts_at, new_ends_at):
    # Row lock first: it pins this booking's day, because only
    # reschedule/cancel of this same row can change or remove it.
    rows = db.execute(
        "SELECT room_id, starts_at FROM bookings WHERE id = %s FOR UPDATE",
        (booking_id,),
    )
    if not rows:
        return False, False
    room_id, old_starts_at = rows[0]

    old_day = _utc_day(old_starts_at)
    new_day = _utc_day(new_starts_at)
    # Old day is locked too, so concurrent bookings on the old day see
    # the freed slot only after this change commits.
    _lock_days(db, room_id, [old_day, new_day])

    count, overlaps = _room_day_state(
        db, room_id, new_day, new_starts_at, new_ends_at, booking_id
    )
    if overlaps or count >= _MAX_PER_DAY:
        return False, False

    db.execute(
        "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
        (new_starts_at, new_ends_at, booking_id),
    )
    return True, True


def _cancel(db, booking_id):
    rows = db.execute(
        "SELECT room_id, starts_at FROM bookings WHERE id = %s FOR UPDATE",
        (booking_id,),
    )
    if not rows:
        return False, False
    room_id, starts_at = rows[0]
    _lock_days(db, room_id, [_utc_day(starts_at)])
    db.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))
    return True, True
