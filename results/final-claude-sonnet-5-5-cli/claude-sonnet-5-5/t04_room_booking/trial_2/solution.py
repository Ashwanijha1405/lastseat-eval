from datetime import datetime


def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    db.begin("read committed")
    try:
        # Serialize all bookings for the same room (released at commit/rollback).
        db.execute("SELECT pg_advisory_xact_lock(%s, %s)", (7001, room_id))
        rows = db.execute(
            """
            INSERT INTO bookings (room_id, starts_at, ends_at)
            SELECT %(room)s, %(s)s, %(e)s
            WHERE NOT EXISTS (
                SELECT 1 FROM bookings
                WHERE room_id = %(room)s
                  AND starts_at < %(e)s
                  AND ends_at > %(s)s
            )
            RETURNING id
            """,
            {"room": room_id, "s": starts_at, "e": ends_at},
        )
        db.commit()
        return bool(rows)
    except Exception:
        db.rollback()
        raise
