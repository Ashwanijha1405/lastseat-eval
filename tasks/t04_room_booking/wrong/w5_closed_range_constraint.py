"""The reference's exclusion constraint, but with closed ranges '[]'.

A closed range includes its end point, so 10:00-11:00 and 11:00-12:00 share
the instant 11:00 and count as overlapping. Never double-books, but refuses
valid back-to-back meetings, alone and concurrently.

EXPECT: solo, liveness
"""

import psycopg.errors


def migrate(db) -> None:
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    db.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap"
        " EXCLUDE USING gist (room_id WITH =, tstzrange(starts_at, ends_at, '[]') WITH &&)"
    )


def book_room(db, room_id, starts_at, ends_at) -> bool:
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
