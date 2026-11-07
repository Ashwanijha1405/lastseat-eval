from __future__ import annotations

import datetime
from psycopg import errors


def _get_utc_day_range(dt: datetime.datetime) -> tuple[datetime.datetime, datetime.datetime]:
    utc_dt = dt.astimezone(datetime.timezone.utc)
    day_start = utc_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + datetime.timedelta(days=1)
    return day_start, day_end


def _overlaps(s1: datetime.datetime, e1: datetime.datetime, s2: datetime.datetime, e2: datetime.datetime) -> bool:
    return s1 < e2 and e1 > s2


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_bookings_room_starts "
        "ON bookings (room_id, starts_at, ends_at)"
    )


def book(db, room_id: int, starts_at: datetime.datetime, ends_at: datetime.datetime) -> bool:
    if starts_at >= ends_at:
        return False

    day_start, day_end = _get_utc_day_range(starts_at)

    for attempt in range(5):
        try:
            db.begin()
            # Lock the room row to serialize concurrent operations for this room
            db.execute("SELECT id FROM rooms WHERE id = %s FOR UPDATE", (room_id,))

            rows = db.execute(
                "SELECT starts_at, ends_at FROM bookings "
                "WHERE room_id = %s AND starts_at >= %s AND starts_at < %s",
                (room_id, day_start, day_end),
            )

            if len(rows) >= 3:
                db.rollback()
                return False

            for b_start, b_end in rows:
                if _overlaps(starts_at, ends_at, b_start, b_end):
                    db.rollback()
                    return False

            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                (room_id, starts_at, ends_at),
            )
            db.commit()
            return True
        except (errors.DeadlockDetected, errors.SerializationFailure, errors.LockNotAvailable):
            try:
                db.rollback()
            except Exception:
                pass
            if attempt == 4:
                return False
            continue
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise


def reschedule(
    db, booking_id: int, new_starts_at: datetime.datetime, new_ends_at: datetime.datetime
) -> bool:
    if new_starts_at >= new_ends_at:
        return False

    day_start, day_end = _get_utc_day_range(new_starts_at)

    for attempt in range(5):
        try:
            db.begin()
            rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
            if not rows:
                db.rollback()
                return False
            room_id = rows[0][0]

            # Lock the room row to serialize concurrent operations for this room
            db.execute("SELECT id FROM rooms WHERE id = %s FOR UPDATE", (room_id,))

            # Find all other bookings of this room on the new day
            other_rows = db.execute(
                "SELECT id, starts_at, ends_at FROM bookings "
                "WHERE room_id = %s AND starts_at >= %s AND starts_at < %s AND id != %s",
                (room_id, day_start, day_end, booking_id),
            )

            # Room can have at most 3 bookings on the new day counting this one
            if len(other_rows) >= 3:
                db.rollback()
                return False

            for _, o_start, o_end in other_rows:
                if _overlaps(new_starts_at, new_ends_at, o_start, o_end):
                    db.rollback()
                    return False

            updated = db.execute(
                "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s RETURNING id",
                (new_starts_at, new_ends_at, booking_id),
            )
            if not updated:
                db.rollback()
                return False

            db.commit()
            return True
        except (errors.DeadlockDetected, errors.SerializationFailure, errors.LockNotAvailable):
            try:
                db.rollback()
            except Exception:
                pass
            if attempt == 4:
                return False
            continue
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise


def cancel(db, booking_id: int) -> bool:
    for attempt in range(5):
        try:
            db.begin()
            rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
            if not rows:
                db.rollback()
                return False
            room_id = rows[0][0]

            # Lock the room row to serialize concurrent operations for this room
            db.execute("SELECT id FROM rooms WHERE id = %s FOR UPDATE", (room_id,))

            deleted = db.execute(
                "DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)
            )
            if deleted:
                db.commit()
                return True
            else:
                db.rollback()
                return False
        except (errors.DeadlockDetected, errors.SerializationFailure, errors.LockNotAvailable):
            try:
                db.rollback()
            except Exception:
                pass
            if attempt == 4:
                return False
            continue
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
