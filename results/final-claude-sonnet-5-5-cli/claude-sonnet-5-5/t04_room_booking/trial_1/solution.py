from datetime import datetime


def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    db.begin("read committed")
    try:
        # Serialize all bookings for this room by locking its row. Once the lock
        # is acquired, the next statement takes a fresh snapshot (read committed),
        # so it sees every booking committed by earlier lock holders.
        db.execute(
            "SELECT id FROM rooms WHERE id = %(room)s FOR NO KEY UPDATE",
            {"room": room_id},
        )
        rows = db.execute(
            "SELECT 1 FROM bookings "
            "WHERE room_id = %(room)s "
            "AND starts_at < %(ends)s AND ends_at > %(starts)s "
            "LIMIT 1",
            {"room": room_id, "starts": starts_at, "ends": ends_at},
        )
        if rows:
            db.rollback()
            return False
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) "
            "VALUES (%(room)s, %(starts)s, %(ends)s)",
            {"room": room_id, "starts": starts_at, "ends": ends_at},
        )
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
