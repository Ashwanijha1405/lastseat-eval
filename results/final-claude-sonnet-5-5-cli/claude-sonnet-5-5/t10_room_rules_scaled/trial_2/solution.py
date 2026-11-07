from datetime import datetime, timedelta, timezone

import psycopg.errors

_UTC = timezone.utc
_MAX_ATTEMPTS = 5


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_starts_idx "
        "ON bookings (room_id, starts_at)"
    )


def _day(dt):
    return dt.astimezone(_UTC).date()


def _bounds(d):
    s = datetime(d.year, d.month, d.day, tzinfo=_UTC)
    return s, s + timedelta(days=1)


def _lock(db, room_id, day):
    db.execute(
        "SELECT pg_advisory_xact_lock(%s, %s)",
        (room_id, day.toordinal()),
    )


_STATS_SQL = """
SELECT
  count(*) FILTER (WHERE starts_at < %(e)s AND ends_at > %(s)s) AS overlaps,
  count(*) FILTER (WHERE starts_at >= %(ds)s AND starts_at < %(de)s) AS day_count
FROM bookings
WHERE room_id = %(room)s AND id <> %(skip)s
"""


def book(db, room_id, starts_at, ends_at):
    day = _day(starts_at)
    ds, de = _bounds(day)
    db.begin()
    _lock(db, room_id, day)
    overlaps, day_count = db.execute(
        _STATS_SQL,
        {"e": ends_at, "s": starts_at, "ds": ds, "de": de,
         "room": room_id, "skip": -1},
    )[0]
    if overlaps > 0 or day_count >= 3:
        db.rollback()
        return False
    db.execute(
        "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
        (room_id, starts_at, ends_at),
    )
    db.commit()
    return True


def reschedule(db, booking_id, new_starts_at, new_ends_at):
    new_day = _day(new_starts_at)
    ds, de = _bounds(new_day)
    for _ in range(_MAX_ATTEMPTS):
        rows = db.execute(
            "SELECT room_id, starts_at FROM bookings WHERE id = %s",
            (booking_id,),
        )
        if not rows:
            return False
        room_id, old_start = rows[0]
        old_day = _day(old_start)

        db.begin()
        for d in sorted({old_day, new_day}):
            _lock(db, room_id, d)

        rows = db.execute(
            "SELECT room_id, starts_at FROM bookings WHERE id = %s",
            (booking_id,),
        )
        if not rows:
            db.rollback()
            return False
        if rows[0][0] != room_id or _day(rows[0][1]) != old_day:
            # Moved before we got the locks; start over with fresh data.
            db.rollback()
            continue

        overlaps, day_count = db.execute(
            _STATS_SQL,
            {"e": new_ends_at, "s": new_starts_at, "ds": ds, "de": de,
             "room": room_id, "skip": booking_id},
        )[0]
        if overlaps > 0 or day_count >= 3:
            db.rollback()
            return False
        db.execute(
            "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
            (new_starts_at, new_ends_at, booking_id),
        )
        db.commit()
        return True
    return False


def cancel(db, booking_id):
    for _ in range(_MAX_ATTEMPTS):
        rows = db.execute(
            "SELECT room_id, starts_at FROM bookings WHERE id = %s",
            (booking_id,),
        )
        if not rows:
            return False
        room_id, start = rows[0]
        day = _day(start)

        db.begin()
        _lock(db, room_id, day)
        rows = db.execute(
            "SELECT room_id, starts_at FROM bookings WHERE id = %s",
            (booking_id,),
        )
        if not rows:
            db.rollback()
            return False
        if rows[0][0] != room_id or _day(rows[0][1]) != day:
            db.rollback()
            continue
        db.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))
        db.commit()
        return True
    return False
