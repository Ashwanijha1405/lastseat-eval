import psycopg.errors
from datetime import datetime

MAX_ATTEMPTS = 3

def migrate(db):
    # Enable the GiST operator classes needed for the exclusion constraint
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # Prevent overlapping bookings for the same room
    db.execute("""
        ALTER TABLE bookings
        ADD CONSTRAINT no_overlap
        EXCLUDE USING GIST (
            room_id WITH =,
            tstzrange(starts_at, ends_at) WITH &&
        )
    """)
    # Lightweight table used only for locking a (room, day) pair
    db.execute("""
        CREATE TABLE IF NOT EXISTS room_day (
            room_id int NOT NULL,
            day date NOT NULL,
            PRIMARY KEY (room_id, day)
        )
    """)

def _lock_room_day(db, room_id: int, day):
    """Ensure the lock row exists and take a FOR UPDATE lock on it."""
    db.execute(
        "INSERT INTO room_day (room_id, day) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (room_id, day)
    )
    db.execute(
        "SELECT 1 FROM room_day WHERE room_id = %s AND day = %s FOR UPDATE",
        (room_id, day)
    )

def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    day = starts_at.date()
    for attempt in range(MAX_ATTEMPTS):
        try:
            db.begin(isolation="read committed")
            _lock_room_day(db, room_id, day)

            # Count existing bookings for that room on that UTC day
            rows = db.execute(
                "SELECT count(*) FROM bookings "
                "WHERE room_id = %s AND (starts_at AT TIME ZONE 'UTC')::date = %s",
                (room_id, day)
            )
            if rows[0][0] >= 3:
                db.rollback()
                return False

            try:
                db.execute(
                    "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                    (room_id, starts_at, ends_at)
                )
            except psycopg.errors.ExclusionViolation:
                db.rollback()
                return False

            db.commit()
            return True

        except psycopg.errors.DeadlockDetected:
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                return False
        except psycopg.errors.SerializationFailure:
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                return False
        except Exception:
            db.rollback()
            raise
    return False

def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool:
    new_day = new_starts_at.date()
    for attempt in range(MAX_ATTEMPTS):
        try:
            db.begin(isolation="read committed")

            # Lock the booking row first
            rows = db.execute(
                "SELECT id, room_id, starts_at FROM bookings WHERE id = %s FOR UPDATE",
                (booking_id,)
            )
            if not rows:
                db.rollback()
                return False

            room_id = rows[0][1]
            old_starts_at = rows[0][2]
            old_day = old_starts_at.date()

            # Lock both days in a consistent order to avoid deadlocks
            for day in sorted({old_day, new_day}):
                _lock_room_day(db, room_id, day)

            # If moving to a different day, enforce the 3‑bookings limit on the new day
            if new_day != old_day:
                rows = db.execute(
                    "SELECT count(*) FROM bookings "
                    "WHERE room_id = %s AND (starts_at AT TIME ZONE 'UTC')::date = %s",
                    (room_id, new_day)
                )
                if rows[0][0] >= 3:
                    db.rollback()
                    return False

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

        except psycopg.errors.DeadlockDetected:
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                return False
        except psycopg.errors.SerializationFailure:
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                return False
        except Exception:
            db.rollback()
            raise
    return False

def cancel(db, booking_id: int) -> bool:
    for attempt in range(MAX_ATTEMPTS):
        try:
            db.begin(isolation="read committed")

            rows = db.execute(
                "SELECT id, room_id, starts_at FROM bookings WHERE id = %s FOR UPDATE",
                (booking_id,)
            )
            if not rows:
                db.rollback()
                return False

            room_id = rows[0][1]
            day = rows[0][2].date()
            _lock_room_day(db, room_id, day)

            db.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))
            db.commit()
            return True

        except psycopg.errors.DeadlockDetected:
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                return False
        except psycopg.errors.SerializationFailure:
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                return False
        except Exception:
            db.rollback()
            raise
    return False
