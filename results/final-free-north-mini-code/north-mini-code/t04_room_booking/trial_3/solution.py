from datetime import datetime
from psycopg.errors import ExclusionViolation, SerializationFailure, DeadlockDetected

def migrate(db) -> None:
    # Ensure the GiST extension for range types is available
    db.begin()
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    db.commit()

    # Add an exclusion constraint to prevent overlapping bookings per room
    db.begin()
    db.execute("""ALTER TABLE bookings
        ADD CONSTRAINT bookings_room_excl
        EXCLUDE USING GIST (room_id WITH =, tstzrange(starts_at, ends_at) WITH &&);""")
    db.commit()

def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin()
            # Try to insert the new booking
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                (room_id, starts_at, ends_at)
            )
            db.commit()
            return True
        except ExclusionViolation:
            # Overlap detected – rollback and reject the request
            db.rollback()
            return False
        except (SerializationFailure, DeadlockDetected):
            # Concurrency failure – rollback and retry
            db.rollback()
        except Exception:
            # Any other error is unexpected and should propagate
            db.rollback()
            raise

    # Should not be reached under normal circumstances
    raise RuntimeError("Failed after retries")
