import psycopg.errors
from datetime import datetime

def migrate(db) -> None:
    # Enable the GiST operator classes for btree types (needed for room_id WITH =)
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # Add an exclusion constraint that prevents overlapping bookings for the same room.
    # The range tsrange(starts_at, ends_at) represents the half-open interval [starts_at, ends_at).
    # The && operator tests for overlap. Two bookings of the same room are allowed only if their ranges do not overlap.
    db.execute("""
        ALTER TABLE bookings
        ADD CONSTRAINT bookings_no_overlap
        EXCLUDE USING gist (
            room_id WITH =,
            tsrange(starts_at, ends_at) WITH &&
        )
    """)

def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    """
    Attempt to book a room for the given time interval.
    Returns True if the booking was created, False if an existing booking overlaps.
    """
    try:
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
            (room_id, starts_at, ends_at)
        )
        return True
    except psycopg.errors.ExclusionViolation:
        # The insert failed because it would overlap with an existing booking.
        # Roll back the aborted transaction so the connection can be used again.
        db.rollback()
        return False
