"""Looks for an overlapping booking, inserts if there is none.

Both requests look before either has inserted, so both see a free room.
Inserting new rows never conflicts with anything, so both commit.

EXPECT: safety
"""


def book_room(db, room_id, starts_at, ends_at) -> bool:
    db.begin()
    clash = db.execute(
        "SELECT 1 FROM bookings WHERE room_id = %s AND starts_at < %s AND ends_at > %s",
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
