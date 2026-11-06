"""An exclusion constraint for overlaps; the daily count from locked rows.

Before adding a booking to a day, it locks that day's existing bookings with
SELECT ... FOR UPDATE and counts the rows that statement returned. A second
request does wait for the first (same rows), but on resuming Postgres
re-checks only the rows it had already found (EvalPlanQual); the booking the
first request added was never in its snapshot, so it still counts 2.

The row locks also deadlock (found by validation, not designed in): a
reschedule locks the rows of the day it joins, which can include a booking
another request is moving the other way (two opposite moves each wait for the
other's row); and it locks that day's rows except its own, then updates its
own row, which a concurrent `book` (locking all of the day's rows) may hold.
DeadlockDetected is not caught, so requests that fit fail.

EXPECT: safety, liveness
"""

import psycopg.errors

_LOCK_DAY_ROWS = (
    "SELECT id FROM bookings WHERE room_id = %s AND id IS DISTINCT FROM %s"
    " AND (starts_at AT TIME ZONE 'UTC')::date = (%s::timestamptz AT TIME ZONE 'UTC')::date FOR UPDATE"
)


def migrate(db) -> None:
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    db.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap"
        " EXCLUDE USING gist (room_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)"
    )


def book(db, room_id, starts_at, ends_at) -> bool:
    db.begin()
    if len(db.execute(_LOCK_DAY_ROWS, (room_id, None, starts_at))) >= 3:
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
    if len(db.execute(_LOCK_DAY_ROWS, (room_id, booking_id, new_starts_at))) >= 3:
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
