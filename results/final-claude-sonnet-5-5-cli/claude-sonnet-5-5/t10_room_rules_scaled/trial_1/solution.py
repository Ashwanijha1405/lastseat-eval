from datetime import datetime, timedelta, timezone

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_starts_idx "
        "ON bookings (room_id, starts_at)"
    )


def _day_bounds(ts: datetime):
    t = ts.astimezone(timezone.utc)
    ds = t.replace(hour=0, minute=0, second=0, microsecond=0)
    de = ds + timedelta(days=1)
    key = (ds - _EPOCH).days
    return ds, de, key


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    ds, de, key = _day_bounds(starts_at)
    db.begin()
    try:
        # Per (room, day) lock: only requests for the same room and day serialize.
        db.execute("SELECT pg_advisory_xact_lock(%s, %s)", (room_id, key))
        overlap = db.execute(
            "SELECT 1 FROM bookings WHERE room_id = %s "
            "AND starts_at < %s AND ends_at > %s LIMIT 1",
            (room_id, ends_at, starts_at),
        )
        if overlap:
            db.rollback()
            return False
        cnt = db.execute(
            "SELECT count(*) FROM bookings WHERE room_id = %s "
            "AND starts_at >= %s AND starts_at < %s",
            (room_id, ds, de),
        )[0][0]
        if cnt >= 3:
            db.rollback()
            return False
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
            (room_id, starts_at, ends_at),
        )
        db.commit()
        return True
    except BaseException:
        try:
            db.rollback()
        except Exception:
            pass
        raise


def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool:
    # The room of a booking never changes, so it can be read before locking.
    rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
    if not rows:
        return False
    room_id = rows[0][0]
    ds, de, key = _day_bounds(new_starts_at)
    db.begin()
    try:
        # Only the destination (room, day) needs the lock: leaving the old day
        # can only reduce its count, so it never needs to block anyone.
        db.execute("SELECT pg_advisory_xact_lock(%s, %s)", (room_id, key))
        cur = db.execute(
            "SELECT id FROM bookings WHERE id = %s FOR UPDATE", (booking_id,)
        )
        if not cur:
            db.rollback()
            return False
        overlap = db.execute(
            "SELECT 1 FROM bookings WHERE room_id = %s AND id <> %s "
            "AND starts_at < %s AND ends_at > %s LIMIT 1",
            (room_id, booking_id, new_ends_at, new_starts_at),
        )
        if overlap:
            db.rollback()
            return False
        others = db.execute(
            "SELECT count(*) FROM bookings WHERE room_id = %s AND id <> %s "
            "AND starts_at >= %s AND starts_at < %s",
            (room_id, booking_id, ds, de),
        )[0][0]
        if others >= 3:
            db.rollback()
            return False
        db.execute(
            "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
            (new_starts_at, new_ends_at, booking_id),
        )
        db.commit()
        return True
    except BaseException:
        try:
            db.rollback()
        except Exception:
            pass
        raise


def cancel(db, booking_id: int) -> bool:
    # Deleting only frees capacity, so a single autocommitted statement suffices.
    rows = db.execute(
        "DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)
    )
    return bool(rows)
