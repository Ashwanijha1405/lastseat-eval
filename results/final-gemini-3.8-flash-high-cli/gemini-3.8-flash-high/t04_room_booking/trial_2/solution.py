from datetime import datetime
from psycopg import errors


def migrate(db) -> None:
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    rows = db.execute(
        "SELECT 1 FROM pg_constraint WHERE conname = 'bookings_no_overlap'"
    )
    if not rows:
        db.execute(
            "ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap "
            "EXCLUDE USING gist (room_id WITH =, (tstzrange(starts_at, ends_at)) WITH &&)"
        )


def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    for _ in range(15):
        try:
            db.begin()
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                (room_id, starts_at, ends_at),
            )
            db.commit()
            return True
        except errors.ExclusionViolation:
            db.rollback()
            return False
        except (errors.SerializationFailure, errors.DeadlockDetected):
            db.rollback()
            continue
    return False
