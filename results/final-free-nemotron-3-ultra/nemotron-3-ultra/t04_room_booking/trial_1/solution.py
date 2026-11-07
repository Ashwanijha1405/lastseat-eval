from datetime import datetime
import psycopg.errors

def migrate(db) -> None:
    # Enable GiST operator classes for integer equality (needed for the exclusion constraint)
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # Prevent overlapping bookings for the same room.
    # The range is [starts_at, ends_at) – adjacent bookings do not overlap.
    db.execute("""
        ALTER TABLE bookings
        ADD CONSTRAINT no_overlapping_bookings
        EXCLUDE USING gist (
            room_id WITH =,
            tsrange(starts_at, ends_at) WITH &&
        )
    """)

def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    try:
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
            (room_id, starts_at, ends_at)
        )
        return True
    except psycopg.errors.ExclusionViolation:
        return False
