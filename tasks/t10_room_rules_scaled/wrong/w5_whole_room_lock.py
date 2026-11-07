"""One lock per room: SELECT ... FROM rooms WHERE id = ... FOR UPDATE.

The strategy Nemotron and Opus used on t09. Every request that touches a room
first locks that room's row, then checks both rules in new statements under
READ COMMITTED. It is safe and live (the room row is a real row, so the lock
exists even when the day has no bookings) and passes every t09 scenario.

But it is coarser than the rules: a booking on Nov 9 and one on Nov 10 of the
same room wait for each other although they can never conflict, and so do a
move into one day and a booking on another, or a cancellation and a booking on
different days. t10 says such requests must never wait. Requests for
different rooms lock different rows and do not wait.

EXPECT: blocking
"""

from datetime import datetime

MAX_PER_DAY = 3

_LOCK_ROOM = "SELECT id FROM rooms WHERE id = %s FOR UPDATE"
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
    db.execute(_LOCK_ROOM, (room_id,))
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
    [(room_id,)] = rows
    db.execute(_LOCK_ROOM, (room_id,))
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
    db.begin()
    rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
    if not rows:
        db.rollback()
        return False
    db.execute(_LOCK_ROOM, (rows[0][0],))
    deleted = db.execute("DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,))
    db.commit()
    return bool(deleted)
