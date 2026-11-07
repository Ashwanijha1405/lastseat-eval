"""Both rules checked inside the writing statement itself, with no lock.

book is one INSERT ... SELECT ... WHERE NOT EXISTS (overlap) AND (count) < 3,
and reschedule one UPDATE with the same conditions. One statement is not a
lock: its subqueries read the statement's snapshot, which cannot see another
request's uncommitted booking, and nothing makes the second statement wait
for the first (they write different rows). Both rules can break.

EXPECT: safety
"""

_FITS = (
    " NOT EXISTS (SELECT 1 FROM bookings o WHERE o.room_id = %(room)s AND o.id IS DISTINCT FROM %(me)s"
    "             AND o.starts_at < %(e)s AND %(s)s < o.ends_at)"
    " AND (SELECT count(*) FROM bookings d WHERE d.room_id = %(room)s AND d.id IS DISTINCT FROM %(me)s"
    "      AND (d.starts_at AT TIME ZONE 'UTC')::date = (%(s)s::timestamptz AT TIME ZONE 'UTC')::date) < 3"
)


def book(db, room_id, starts_at, ends_at) -> bool:
    db.begin()
    rows = db.execute(
        "INSERT INTO bookings (room_id, starts_at, ends_at) SELECT %(room)s, %(s)s, %(e)s WHERE" + _FITS
        + " RETURNING id",
        {"room": room_id, "s": starts_at, "e": ends_at, "me": None},
    )
    db.commit()
    return bool(rows)


def reschedule(db, booking_id, new_starts_at, new_ends_at) -> bool:
    db.begin()
    rows = db.execute(
        "UPDATE bookings b SET starts_at = %(s)s, ends_at = %(e)s"
        " WHERE b.id = %(me)s AND b.room_id = %(room)s AND" + _FITS + " RETURNING b.id",
        {"room": _room_of(db, booking_id), "s": new_starts_at, "e": new_ends_at, "me": booking_id},
    )
    db.commit()
    return bool(rows)


def _room_of(db, booking_id):
    rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
    return rows[0][0] if rows else None


def cancel(db, booking_id) -> bool:
    return bool(db.execute("DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)))
