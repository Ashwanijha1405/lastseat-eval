from __future__ import annotations

from datetime import datetime, timedelta, timezone
from psycopg import errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_bookings_room_starts_ends "
        "ON bookings (room_id, starts_at, ends_at)"
    )


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    if starts_at >= ends_at:
        return False

    day = starts_at.astimezone(timezone.utc).date()
    day_int = day.toordinal()
    day_start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    for _ in range(5):
        try:
            db.begin()
            db.execute("SELECT pg_advisory_xact_lock(%s, %s)", (room_id, day_int))

            check_sql = """
            SELECT
                count(*) AS day_count,
                count(*) FILTER (WHERE starts_at < %s AND ends_at > %s) AS overlap_count
            FROM bookings
            WHERE room_id = %s
              AND starts_at >= %s
              AND starts_at < %s
            """
            rows = db.execute(
                check_sql,
                (ends_at, starts_at, room_id, day_start, day_end),
            )
            day_count, overlap_count = rows[0]

            if day_count >= 3 or overlap_count > 0:
                db.rollback()
                return False

            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                (room_id, starts_at, ends_at),
            )
            db.commit()
            return True
        except errors.Error:
            try:
                db.rollback()
            except Exception:
                pass
            continue
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            return False

    return False


def reschedule(
    db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime
) -> bool:
    if new_starts_at >= new_ends_at:
        return False

    new_day = new_starts_at.astimezone(timezone.utc).date()
    new_day_int = new_day.toordinal()
    new_day_start = datetime(
        new_day.year, new_day.month, new_day.day, 0, 0, 0, tzinfo=timezone.utc
    )
    new_day_end = new_day_start + timedelta(days=1)

    for _ in range(5):
        try:
            db.begin()
            rows = db.execute(
                "SELECT room_id, starts_at FROM bookings WHERE id = %s",
                (booking_id,),
            )
            if not rows:
                db.rollback()
                return False

            room_id, old_starts_at = rows[0]
            old_day = old_starts_at.astimezone(timezone.utc).date()
            old_day_int = old_day.toordinal()

            # Acquire advisory locks in sorted order to avoid deadlocks across multiple days
            days_to_lock = sorted({old_day_int, new_day_int})
            for d in days_to_lock:
                db.execute("SELECT pg_advisory_xact_lock(%s, %s)", (room_id, d))

            # Re-verify booking details under the acquired lock
            rows = db.execute(
                "SELECT room_id, starts_at FROM bookings WHERE id = %s",
                (booking_id,),
            )
            if not rows:
                db.rollback()
                return False

            curr_room_id, curr_starts_at = rows[0]
            curr_day_int = (
                curr_starts_at.astimezone(timezone.utc).date().toordinal()
            )

            if curr_room_id != room_id or curr_day_int != old_day_int:
                db.rollback()
                continue

            check_sql = """
            SELECT
                count(*) AS new_day_count,
                count(*) FILTER (WHERE starts_at < %s AND ends_at > %s) AS overlap_count
            FROM bookings
            WHERE room_id = %s
              AND id != %s
              AND starts_at >= %s
              AND starts_at < %s
            """
            rows = db.execute(
                check_sql,
                (
                    new_ends_at,
                    new_starts_at,
                    room_id,
                    booking_id,
                    new_day_start,
                    new_day_end,
                ),
            )
            new_day_count, overlap_count = rows[0]

            if new_day_count >= 3 or overlap_count > 0:
                db.rollback()
                return False

            db.execute(
                "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
                (new_starts_at, new_ends_at, booking_id),
            )
            db.commit()
            return True
        except errors.Error:
            try:
                db.rollback()
            except Exception:
                pass
            continue
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            return False

    return False


def cancel(db, booking_id: int) -> bool:
    try:
        rows = db.execute(
            "DELETE FROM bookings WHERE id = %s RETURNING id",
            (booking_id,),
        )
        return bool(rows)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False
