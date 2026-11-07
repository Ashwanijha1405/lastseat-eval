from datetime import datetime
import psycopg.errors

def migrate(db):
    # Enable GiST support for btree operators (needed for room_id =)
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # Add exclusion constraint to prevent overlapping bookings for the same room
    try:
        db.execute("""
            ALTER TABLE bookings
            ADD CONSTRAINT no_overlap
            EXCLUDE USING gist (room_id WITH =, tsrange(starts_at, ends_at) WITH &&)
        """)
    except psycopg.errors.DuplicateObject:
        # Constraint already exists (e.g., from a previous migration run)
        pass

def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    # Retry a few times on transient errors (deadlock, serialization failure).
    # In read committed isolation (the default) serialization failures don't occur,
    # but deadlocks are theoretically possible.
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%(room_id)s, %(starts_at)s, %(ends_at)s)",
                {"room_id": room_id, "starts_at": starts_at, "ends_at": ends_at}
            )
            return True
        except psycopg.errors.ExclusionViolation:
            # Overlap with an existing booking (committed or being inserted by a concurrent transaction)
            return False
        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            # Transient error – retry
            continue
    # If we exhausted retries due to transient errors, raise an exception.
    # The task doesn't specify what to do in this case; raising is acceptable.
    raise RuntimeError("Failed to book room after multiple retries")
