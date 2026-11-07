"""SERIALIZABLE, no explicit locks, bounded retry (not a reference; graded to see what happens).

Each call runs check-then-write in one SERIALIZABLE transaction. Postgres's
serializable snapshot isolation (SSI) takes no blocking locks for reads; it
tracks what each transaction read (SIREAD "predicate locks") and aborts one
transaction with SerializationFailure (40001) if the reads and writes of
concurrent transactions could not have happened in any one-at-a-time order.
That covers the phantom count: two bookings for the last place of a day each
read the day's count and insert, a read-write cycle, so one is aborted.

On 40001 (or a deadlock) it rolls back and retries, at most MAX_TRIES times,
then raises. Writes to the same row can still wait for each other (row locks
exist under SERIALIZABLE too); independent requests touch different rows.
"""

from datetime import datetime

import psycopg.errors

MAX_PER_DAY = 3
MAX_TRIES = 8  # 4 db calls per try at most, within the 60-call limit

_CHECK = """
SELECT
  EXISTS (SELECT 1 FROM bookings
          WHERE room_id = %(room)s AND id IS DISTINCT FROM %(me)s
            AND starts_at < %(e)s AND %(s)s < ends_at),
  (SELECT count(*) FROM bookings
   WHERE room_id = %(room)s AND id IS DISTINCT FROM %(me)s
     AND (starts_at AT TIME ZONE 'UTC')::date = (%(s)s::timestamptz AT TIME ZONE 'UTC')::date)
"""
_RETRY = (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected)


def _retrying(db, attempt):
    for n in range(MAX_TRIES):
        db.begin("serializable")
        try:
            return attempt()
        except _RETRY:
            db.rollback()
            if n == MAX_TRIES - 1:
                raise


def _fits(db, room_id, starts_at, ends_at, me) -> bool:
    [(overlaps, same_day)] = db.execute(_CHECK, {"room": room_id, "s": starts_at, "e": ends_at, "me": me})
    return not overlaps and same_day < MAX_PER_DAY


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    def attempt():
        if not _fits(db, room_id, starts_at, ends_at, None):
            db.rollback()
            return False
        db.execute("INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                   (room_id, starts_at, ends_at))
        db.commit()
        return True
    return _retrying(db, attempt)


def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool:
    def attempt():
        rows = db.execute("SELECT room_id FROM bookings WHERE id = %s", (booking_id,))
        if not rows or not _fits(db, rows[0][0], new_starts_at, new_ends_at, booking_id):
            db.rollback()
            return False
        db.execute("UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
                   (new_starts_at, new_ends_at, booking_id))
        db.commit()
        return True
    return _retrying(db, attempt)


def cancel(db, booking_id: int) -> bool:
    def attempt():
        deleted = db.execute("DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,))
        db.commit()
        return bool(deleted)
    return _retrying(db, attempt)
