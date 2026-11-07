from datetime import datetime

import psycopg
import psycopg.errors


def migrate(db) -> None:
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    db.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_no_room_overlap "
        "EXCLUDE USING gist ("
        "room_id WITH =, "
        "tstzrange(starts_at, ends_at, '[)') WITH &&"
        ")"
    )


def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    try:
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) "
            "VALUES (%s, %s, %s)",
            (room_id, starts_at, ends_at),
        )
    except psycopg.errors.ExclusionViolation:
        db.rollback()
        return False
    return True
