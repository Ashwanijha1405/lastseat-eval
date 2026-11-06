"""Runs the overlap query with FOR UPDATE, then inserts.

FOR UPDATE locks the rows the query returns. When the room is free the
result is empty, so nothing is locked and the other request never waits.

EXPECT: safety
"""


def book_room(db, room_id, starts_at, ends_at) -> bool:
    db.begin()
    clash = db.execute(
        "SELECT id FROM bookings WHERE room_id = %s AND starts_at < %s AND ends_at > %s FOR UPDATE",
        (room_id, ends_at, starts_at),
    )
    if clash:
        db.rollback()
        return False
    db.execute(
        "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
        (room_id, starts_at, ends_at),
    )
    db.commit()
    return True
