from datetime import datetime

from psycopg import errors


def migrate(db) -> None:
    # btree_gist is needed so GiST can index the integer room_id with "=".
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # Half-open ranges: [starts_at, ends_at) so back-to-back bookings do not overlap.
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
        # The exclusion constraint checks overlaps atomically. If a conflicting
        # booking is in progress, this insert waits for it to finish, then either
        # succeeds (it rolled back) or raises ExclusionViolation (it committed).
        db.execute(
            "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
            (room_id, starts_at, ends_at),
        )
        db.commit()
        return True
    except errors.ExclusionViolation:
        db.rollback()
        return False
