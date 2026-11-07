import psycopg
import psycopg.errors
from datetime import datetime, timezone, timedelta, date

_EPOCH = date(1970, 1, 1)
_RETRYABLE = (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected)
_MAX_ATTEMPTS = 6


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_start_idx "
        "ON bookings (room_id, starts_at)"
    )


def _day_info(ts: datetime):
    d = ts.astimezone(timezone.utc).date()
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return (d - _EPOCH).days, start, start + timedelta(days=1)


def _lock(db, room_id: int, dayno: int):
    db.execute("SELECT pg_advisory_xact_lock(%s::int, %s::int)", (room_id, dayno))


def _check(db, room_id, ds, de, ns, ne, exclude_id):
    rows = db.execute(
        "SELECT count(*), "
        "COALESCE(bool_or(starts_at < %(ne)s AND ends_at > %(ns)s), false) "
        "FROM bookings "
        "WHERE room_id = %(r)s AND id <> %(x)s "
        "AND starts_at >= %(ds)s AND starts_at < %(de)s",
        {"r": room_id, "x": exclude_id, "ds": ds, "de": de, "ns": ns, "ne": ne},
    )
    cnt, overlap = rows[0]
    return int(cnt), bool(overlap)


def _safe_rollback(db):
    try:
        db.rollback()
    except Exception:
        pass


def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    dayno, ds, de = _day_info(starts_at)
    for _ in range(_MAX_ATTEMPTS):
        try:
            db.begin("read committed")
            _lock(db, room_id, dayno)
            cnt, overlap = _check(db, room_id, ds, de, starts_at, ends_at, -1)
            if overlap or cnt >= 3:
                db.rollback()
                return False
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                (room_id, starts_at, ends_at),
            )
            db.commit()
            return True
        except _RETRYABLE:
            _safe_rollback(db)
            continue
        except Exception:
            _safe_rollback(db)
            raise
    return False


def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool:
    new_day, nds, nde = _day_info(new_starts_at)
    for _ in range(_MAX_ATTEMPTS):
        try:
            db.begin("read committed")
            rows = db.execute(
                "SELECT room_id, starts_at FROM bookings WHERE id = %s", (booking_id,)
            )
            if not rows:
                db.rollback()
                return False
            room_id, old_start = rows[0]
            old_day = _day_info(old_start)[0]
            for d in sorted({old_day, new_day}):
                _lock(db, room_id, d)
            rows = db.execute(
                "SELECT starts_at FROM bookings WHERE id = %s", (booking_id,)
            )
            if not rows:
                db.rollback()
                return False
            if _day_info(rows[0][0])[0] != old_day:
                # Moved by someone else in the meantime; retry with fresh day.
                db.rollback()
                continue
            cnt, overlap = _check(
                db, room_id, nds, nde, new_starts_at, new_ends_at, booking_id
            )
            if overlap or cnt + 1 > 3:
                db.rollback()
                return False
            db.execute(
                "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
                (new_starts_at, new_ends_at, booking_id),
            )
            db.commit()
            return True
        except _RETRYABLE:
            _safe_rollback(db)
            continue
        except Exception:
            _safe_rollback(db)
            raise
    return False


def cancel(db, booking_id: int) -> bool:
    for _ in range(_MAX_ATTEMPTS):
        try:
            db.begin("read committed")
            rows = db.execute(
                "SELECT room_id, starts_at FROM bookings WHERE id = %s", (booking_id,)
            )
            if not rows:
                db.rollback()
                return False
            room_id, start = rows[0]
            dayno = _day_info(start)[0]
            _lock(db, room_id, dayno)
            rows = db.execute(
                "SELECT starts_at FROM bookings WHERE id = %s", (booking_id,)
            )
            if not rows:
                db.rollback()
                return False
            if _day_info(rows[0][0])[0] != dayno:
                db.rollback()
                continue
            rows = db.execute(
                "DELETE FROM bookings WHERE id = %s RETURNING id", (booking_id,)
            )
            db.commit()
            return bool(rows)
        except _RETRYABLE:
            _safe_rollback(db)
            continue
        except Exception:
            _safe_rollback(db)
            raise
    return False
