"""A single INSERT ... SELECT ... WHERE NOT EXISTS (overlapping booking).

One statement is not a lock. The NOT EXISTS subquery reads from the
statement's snapshot, which cannot see the other request's uncommitted row,
and nothing makes the second INSERT wait for the first. Both insert.

EXPECT: safety
"""


def book_room(db, room_id, starts_at, ends_at) -> bool:
    rows = db.execute(
        "INSERT INTO bookings (room_id, starts_at, ends_at)"
        " SELECT %(room)s, %(start)s, %(end)s"
        " WHERE NOT EXISTS (SELECT 1 FROM bookings"
        "   WHERE room_id = %(room)s AND starts_at < %(end)s AND ends_at > %(start)s)"
        " RETURNING id",
        {"room": room_id, "start": starts_at, "end": ends_at},
    )
    return bool(rows)
