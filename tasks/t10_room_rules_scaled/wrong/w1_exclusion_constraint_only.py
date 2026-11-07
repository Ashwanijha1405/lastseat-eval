"""An exclusion constraint for overlaps; the daily count is checked without a lock.

migrate() adds EXCLUDE USING gist (room_id WITH =, [starts_at, ends_at) WITH &&),
which makes overlapping bookings impossible however requests interleave. But
the 3-per-day rule is a count, and no constraint covers it here: two requests
both count 2 bookings on the day, neither waits for the other (they insert or
update different rows, which do not overlap), and the day ends with 4.

EXPECT: safety
"""

import psycopg.errors

_COUNT_DAY = (
    "SELECT count(*) FROM bookings WHERE room_id = %s AND id IS DISTINCT FROM %s"
    " AND (starts_at AT TIME ZONE 'UTC')::date = (%s::timestamptz AT TIME ZONE 'UTC')::date"
)


def migrate(db) -> None:
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    db.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap"
        " EXCLUDE USING gist (room_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)"
    )


def book(db, room_id, starts_at, ends_at) -> bool:
    db.begin()
    [(same_day,)] = db.execute(_COUNT_DAY, (room_id, None, starts_at))
    if same_day >= 3:
        db.rollback()
        return False
    try:
        db.execute("INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                   (room_id, starts_at, ends_at))
    except psycopg.errors.ExclusionViolation:
        db.rollback()
        return False
    db.commit()
    return True


def reschedule(db, booking_id, new_starts_at, new_ends_at) -> bool:
    db.begin()
    rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
    if not rows:
        db.rollback()
        return False
    [(room_id,)] = rows
    [(same_day,)] = db.execute(_COUNT_DAY, (room_id, booking_id, new_starts_at))
    if same_day >= 3:
        db.rollback()
        return False
    try:
        moved = db.execute("UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s RETURNING id",
                           (new_starts_at, new_ends_at, booking_id))
    except psycopg.errors.ExclusionViolation:
        db.rollback()
        return False
    if not moved:
        db.rollback()
        return False
    db.commit()
    return True


def cancel(db, booking_id) -> bool:
    return bool(db.execute("DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)))
