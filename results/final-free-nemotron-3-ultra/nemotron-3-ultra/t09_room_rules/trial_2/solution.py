import psycopg.errors
from datetime import timezone

def migrate(db) -> None:
    # Enable the GiST operator classes for btree (needed for exclusion constraint on scalar + range)
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # Exclusion constraint to prevent overlapping bookings for the same room.
    # Uses a half-open interval [starts_at, ends_at) via tsrange with '[)' bounds.
    db.execute("""
        ALTER TABLE bookings
        ADD CONSTRAINT no_overlap
        EXCLUDE USING gist (
            room_id WITH =,
            tsrange(starts_at, ends_at, '[)') WITH &&
        )
    """)

    # Table to track per-room per-day booking counts (max 3).
    db.execute("""
        CREATE TABLE room_day_bookings (
            room_id      int NOT NULL REFERENCES rooms(id),
            day          date NOT NULL,
            booking_count int NOT NULL DEFAULT 0 CHECK (booking_count >= 0 AND booking_count <= 3),
            PRIMARY KEY (room_id, day)
        )
    """)

    # Populate with counts from existing bookings.
    db.execute("""
        INSERT INTO room_day_bookings (room_id, day, booking_count)
        SELECT room_id, starts_at::date, count(*)
        FROM bookings
        GROUP BY room_id, starts_at::date
    """)


def _utc_date(dt) -> 'datetime.date':
    """Return the UTC calendar date of a timezone-aware datetime."""
    return dt.astimezone(timezone.utc).date()


def book(db, room_id: int, starts_at, ends_at) -> bool:
    day = _utc_date(starts_at)

    for _ in range(3):  # bounded retry for deadlocks
        try:
            db.begin()

            # Ensure a row exists for this room/day, then lock it.
            db.execute(
                "INSERT INTO room_day_bookings (room_id, day, booking_count) "
                "VALUES (%s, %s, 0) ON CONFLICT (room_id, day) DO NOTHING",
                (room_id, day)
            )
            rows = db.execute(
                "SELECT booking_count FROM room_day_bookings "
                "WHERE room_id = %s AND day = %s FOR UPDATE",
                (room_id, day)
            )
            if not rows:
                db.rollback()
                return False
            count = rows[0][0]
            if count >= 3:
                db.rollback()
                return False

            # Try to insert the booking; exclusion constraint catches overlaps.
            try:
                db.execute(
                    "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                    (room_id, starts_at, ends_at)
                )
            except psycopg.errors.ExclusionViolation:
                db.rollback()
                return False

            # Increment the daily count.
            db.execute(
                "UPDATE room_day_bookings SET booking_count = booking_count + 1 "
                "WHERE room_id = %s AND day = %s",
                (room_id, day)
            )

            db.commit()
            return True

        except psycopg.errors.DeadlockDetected:
            db.rollback()
            continue
        except Exception:
            db.rollback()
            return False

    return False


def reschedule(db, booking_id: int, new_starts_at, new_ends_at) -> bool:
    for _ in range(3):
        try:
            db.begin()

            # Lock the booking row to prevent concurrent modifications.
            rows = db.execute(
                "SELECT id, room_id, starts_at, ends_at FROM bookings WHERE id = %s FOR UPDATE",
                (booking_id,)
            )
            if not rows:
                db.rollback()
                return False

            _, room_id, old_starts, old_ends = rows[0]
            old_day = _utc_date(old_starts)
            new_day = _utc_date(new_starts_at)

            if old_day == new_day:
                # Same day: only need to check overlap via exclusion constraint.
                try:
                    db.execute(
                        "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
                        (new_starts_at, new_ends_at, booking_id)
                    )
                except psycopg.errors.ExclusionViolation:
                    db.rollback()
                    return False
                db.commit()
                return True

            # Different days: lock both day rows in a consistent order (earlier day first).
            days = sorted([old_day, new_day])
            for d in days:
                db.execute(
                    "INSERT INTO room_day_bookings (room_id, day, booking_count) "
                    "VALUES (%s, %s, 0) ON CONFLICT (room_id, day) DO NOTHING",
                    (room_id, d)
                )
            for d in days:
                db.execute(
                    "SELECT booking_count FROM room_day_bookings "
                    "WHERE room_id = %s AND day = %s FOR UPDATE",
                    (room_id, d)
                )

            # Check the new day's count (old day's count is irrelevant for the limit).
            rows = db.execute(
                "SELECT booking_count FROM room_day_bookings WHERE room_id = %s AND day = %s",
                (room_id, new_day)
            )
            new_count = rows[0][0]
            if new_count >= 3:
                db.rollback()
                return False

            # Update the booking; exclusion constraint validates the new interval.
            try:
                db.execute(
                    "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
                    (new_starts_at, new_ends_at, booking_id)
                )
            except psycopg.errors.ExclusionViolation:
                db.rollback()
                return False

            # Adjust daily counts.
            db.execute(
                "UPDATE room_day_bookings SET booking_count = booking_count - 1 "
                "WHERE room_id = %s AND day = %s",
                (room_id, old_day)
            )
            db.execute(
                "UPDATE room_day_bookings SET booking_count = booking_count + 1 "
                "WHERE room_id = %s AND day = %s",
                (room_id, new_day)
            )

            db.commit()
            return True

        except psycopg.errors.DeadlockDetected:
            db.rollback()
            continue
        except Exception:
            db.rollback()
            return False

    return False


def cancel(db, booking_id: int) -> bool:
    for _ in range(3):
        try:
            db.begin()

            rows = db.execute(
                "SELECT id, room_id, starts_at FROM bookings WHERE id = %s FOR UPDATE",
                (booking_id,)
            )
            if not rows:
                db.rollback()
                return False

            _, room_id, starts_at = rows[0]
            day = _utc_date(starts_at)

            # Lock the day's count row.
            db.execute(
                "SELECT booking_count FROM room_day_bookings "
                "WHERE room_id = %s AND day = %s FOR UPDATE",
                (room_id, day)
            )

            db.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))

            db.execute(
                "UPDATE room_day_bookings SET booking_count = booking_count - 1 "
                "WHERE room_id = %s AND day = %s",
                (room_id, day)
            )

            db.commit()
            return True

        except psycopg.errors.DeadlockDetected:
            db.rollback()
            continue
        except Exception:
            db.rollback()
            return False

    return False
