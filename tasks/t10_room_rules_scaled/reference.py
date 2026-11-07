"""Reference: one lock per (room, UTC day), taken on the day a booking moves INTO.

Both rules are about one room on one day (a booking never crosses midnight UTC,
so two bookings on different days cannot overlap). The only writes that can
break a rule on day D are those that add a booking to D: `book` on D, or
`reschedule` to a time on D. Each takes the lock for (room, D) first, then
checks both rules in a new statement, so under READ COMMITTED it sees every
booking committed by whoever held that lock before.

The lock is a transaction-level advisory lock: a lock on a pair of numbers
(room id, days since 2000-01-01), released at commit or rollback. It exists
even when D has no bookings yet; a row lock could only lock rows that exist.

Moving a booking OUT of a day, or cancelling it, only removes a booking from
that day, which can never break either rule there, so neither takes that
day's lock. Each request therefore takes at most one lock: no deadlock.
"""

from datetime import datetime

MAX_PER_DAY = 3

_LOCK_ROOM_DAY = (
    "SELECT pg_advisory_xact_lock(%s::int, ((%s::timestamptz AT TIME ZONE 'UTC')::date - DATE '2000-01-01'))"
)
# Overlaps with, and bookings on the same UTC day as, the time [s, e) in the
# room, leaving out booking `me` (None when booking a new slot).
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
    rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
    if not rows:
        db.rollback()
        return False
    [(room_id,)] = rows  # never changes, so it cannot be stale
    db.execute(_LOCK_ROOM_DAY, (room_id, new_starts_at))
    if not _fits(db, room_id, new_starts_at, new_ends_at, booking_id):
        db.rollback()
        return False
    # Zero rows if a cancel committed after our first read: report it, change nothing.
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
