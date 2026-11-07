from __future__ import annotations

from datetime import datetime


def _lock_room(db, room_id: int) -> None:
    # Serializes all writers of this room. Each transaction locks only one room,
    # so no deadlocks. Under READ COMMITTED every later statement sees the
    # latest committed data once the lock is held.
    db.execute(
        "SELECT 1 FROM rooms WHERE id = %(r)s FOR NO KEY UPDATE",
        {"r": room_id},
    )


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    db.begin("read committed")
    try:
        _lock_room(db, room_id)
        rows = db.execute(
            """
            INSERT INTO bookings (room_id, starts_at, ends_at)
            SELECT %(r)s, %(s)s::timestamptz, %(e)s::timestamptz
            WHERE NOT EXISTS (
                SELECT 1 FROM bookings b
                WHERE b.room_id = %(r)s
                  AND b.starts_at < %(e)s::timestamptz
                  AND b.ends_at > %(s)s::timestamptz
            )
            AND (
                SELECT count(*) FROM bookings b
                WHERE b.room_id = %(r)s
                  AND (b.starts_at AT TIME ZONE 'UTC')::date
                      = (%(s)s::timestamptz AT TIME ZONE 'UTC')::date
            ) < 3
            RETURNING id
            """,
            {"r": room_id, "s": starts_at, "e": ends_at},
        )
        ok = bool(rows)
        db.commit()
        return ok
    except BaseException:
        db.rollback()
        raise


def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool:
    # A booking never changes room, so the room can be read without a lock.
    rows = db.execute("SELECT room_id FROM bookings WHERE id = %(i)s", {"i": booking_id})
    if not rows:
        return False
    room_id = rows[0][0]

    db.begin("read committed")
    try:
        _lock_room(db, room_id)
        # Re-check existence now that we hold the room lock (it may have been cancelled).
        cur = db.execute(
            "SELECT id FROM bookings WHERE id = %(i)s FOR UPDATE",
            {"i": booking_id},
        )
        if not cur:
            db.rollback()
            return False

        upd = db.execute(
            """
            UPDATE bookings
               SET starts_at = %(s)s::timestamptz,
                   ends_at   = %(e)s::timestamptz
             WHERE id = %(i)s
               AND NOT EXISTS (
                   SELECT 1 FROM bookings b
                   WHERE b.room_id = %(r)s
                     AND b.id <> %(i)s
                     AND b.starts_at < %(e)s::timestamptz
                     AND b.ends_at > %(s)s::timestamptz
               )
               AND (
                   SELECT count(*) FROM bookings b
                   WHERE b.room_id = %(r)s
                     AND b.id <> %(i)s
                     AND (b.starts_at AT TIME ZONE 'UTC')::date
                         = (%(s)s::timestamptz AT TIME ZONE 'UTC')::date
               ) < 3
            RETURNING id
            """,
            {"i": booking_id, "r": room_id, "s": new_starts_at, "e": new_ends_at},
        )
        ok = bool(upd)
        db.commit()
        return ok
    except BaseException:
        db.rollback()
        raise


def cancel(db, booking_id: int) -> bool:
    rows = db.execute("SELECT room_id FROM bookings WHERE id = %(i)s", {"i": booking_id})
    if not rows:
        return False
    room_id = rows[0][0]

    db.begin("read committed")
    try:
        _lock_room(db, room_id)
        deleted = db.execute(
            "DELETE FROM bookings WHERE id = %(i)s RETURNING id",
            {"i": booking_id},
        )
        ok = bool(deleted)
        db.commit()
        return ok
    except BaseException:
        db.rollback()
        raise
