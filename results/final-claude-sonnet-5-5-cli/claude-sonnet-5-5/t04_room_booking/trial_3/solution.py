from datetime import datetime


def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    db.begin("read committed")
    try:
        # Serialize bookings per room. The lock is released at commit/rollback,
        # and the statements below take their snapshots after the lock is held,
        # so they see every previously committed booking for this room.
        db.execute("SELECT pg_advisory_xact_lock(%s, %s)", (727001, room_id))

        rows = db.execute(
            """
            SELECT 1
            FROM bookings
            WHERE room_id = %(room)s
              AND starts_at < %(ends)s
              AND ends_at > %(starts)s
            LIMIT 1
            """,
            {"room": room_id, "starts": starts_at, "ends": ends_at},
        )
        if rows:
            db.rollback()
            return False

        db.execute(
            """
            INSERT INTO bookings (room_id, starts_at, ends_at)
            VALUES (%(room)s, %(starts)s, %(ends)s)
            """,
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
