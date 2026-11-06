"""Like the reference, but reschedule locks the day it leaves, then the day it joins.

Locking both days is harmless on its own, but the order follows the move, so
two moves between the same two days in opposite directions take the same two
locks in opposite orders: each holds one and waits for the other. Postgres
detects the deadlock and aborts one of them with DeadlockDetected, which is
not caught or retried, so a request that fits fails.

EXPECT: liveness
"""

from datetime import datetime

MAX_PER_DAY = 3

_LOCK_ROOM_DAY = (
    "SELECT pg_advisory_xact_lock(%s::int, ((%s::timestamptz AT TIME ZONE 'UTC')::date - DATE '2000-01-01'))"
)
_CHECK = """
SELECT
  EXISTS (SELECT 1 FROM bookings
          WHERE room_id = %(room)s AND id IS DISTINCT FROM %(me)s
            AND starts_at < %(e)s AND %(s)s < ends_at),
  (SELECT count(*) FROM bookings
   WHERE room_id = %(room)s AND id IS DISTINCT FROM %(me)s
     AND (starts_at AT TIME ZONE 'UTC')::date = (%(s)s::timestamptz AT TIME ZONE 'UTC')::date)
"""


def _fits(db, room_id: int, starts_at: datetime, ends_at: datetime, me: int | None) -> bool:
    [(overlaps, same_day)] = db.execute(_CHECK, {"room": room_id, "s": starts_at, "e": ends_at, "me": me})
    return not overlaps and same_day < MAX_PER_DAY


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    db.begin()
    db.execute(_LOCK_ROOM_DAY, (room_id, starts_at))
    if not _fits(db, room_id, starts_at, ends_at, None):
        db.rollback()
        return False
    db.execute("INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)", (room_id, starts_at, ends_at))
    db.commit()
    return True


def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool:
    db.begin()
    rows = db.execute("SELECT room_id, starts_at FROM bookings WHERE id = %s", (booking_id,))
    if not rows:
        db.rollback()
        return False
    [(room_id, old_starts_at)] = rows
    db.execute(_LOCK_ROOM_DAY, (room_id, old_starts_at))  # the day it leaves...
    db.execute(_LOCK_ROOM_DAY, (room_id, new_starts_at))  # ...then the day it joins
    if not _fits(db, room_id, new_starts_at, new_ends_at, booking_id):
        db.rollback()
        return False
    moved = db.execute(
        "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s RETURNING id",
        (new_starts_at, new_ends_at, booking_id),
    )
    if not moved:
        db.rollback()
        return False
    db.commit()
    return True


def cancel(db, booking_id: int) -> bool:
    return bool(db.execute("DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)))
