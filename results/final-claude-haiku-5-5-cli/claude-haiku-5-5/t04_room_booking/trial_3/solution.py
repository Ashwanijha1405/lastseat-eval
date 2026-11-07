from datetime import datetime

from psycopg.errors import ExclusionViolation


def migrate(db) -> None:
    # btree_gist is a trusted extension, so the database owner can create it.
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # Half-open ranges: [starts_at, ends_at). Adjacent bookings do not overlap.
    db.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_no_room_overlap "
        "EXCLUDE USING gist ("
        "room_id WITH =, "
        "tstzrange(starts_at, ends_at, '[)') WITH &&"
        ")"
    )


def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    db.begin()
    try:
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
            (room_id, starts_at, ends_at),
        )
        db.commit()
        return True
    except ExclusionViolation:
        db.rollback()
        return False
