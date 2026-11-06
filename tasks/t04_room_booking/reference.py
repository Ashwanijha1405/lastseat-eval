"""Reference: an exclusion constraint makes overlapping rows impossible.

The constraint is checked through a GiST index, and the index sees other
transactions' uncommitted rows. A second, overlapping INSERT therefore waits
for the first transaction: if it commits, the second gets ExclusionViolation
(refused cleanly here); if it rolls back, the second INSERT goes through.
btree_gist lets the GiST index compare room_id with `=`.
"""

from datetime import datetime

import psycopg.errors


def migrate(db) -> None:
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    db.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap"
        " EXCLUDE USING gist (room_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)"
    )


def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    db.begin()
    try:
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
            (room_id, starts_at, ends_at),
        )
    except psycopg.errors.ExclusionViolation:
        db.rollback()
        return False
    db.commit()
    return True
