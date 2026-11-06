"""Check-then-insert under REPEATABLE READ.

REPEATABLE READ raises an error only when two transactions update the same
existing row. Two INSERTs of different new rows never collide, and both
snapshots show a free room.

EXPECT: safety
"""


def book_room(db, room_id, starts_at, ends_at) -> bool:
    db.begin("repeatable read")
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
