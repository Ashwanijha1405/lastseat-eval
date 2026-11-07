import psycopg.errors as errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS bookings_room_time_idx "
        "ON bookings (room_id, starts_at, ends_at)"
    )


_RETRYABLE = (
    errors.SerializationFailure,
    errors.DeadlockDetected,
    errors.LockNotAvailable,
)


def book_room(db, room_id, starts_at, ends_at) -> bool:
    last_exc = None
    for _ in range(8):
        try:
            db.begin("read committed")
            # Serialize all bookings for this room.
            db.execute(
                "SELECT id FROM rooms WHERE id = %(room)s FOR UPDATE",
                {"room": room_id},
            )
            conflict = db.execute(
                "SELECT 1 FROM bookings "
                "WHERE room_id = %(room)s "
                "AND starts_at < %(e)s AND ends_at > %(s)s "
                "LIMIT 1",
                {"room": room_id, "s": starts_at, "e": ends_at},
            )
            if conflict:
                db.rollback()
                return False
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) "
                "VALUES (%(room)s, %(s)s, %(e)s)",
                {"room": room_id, "s": starts_at, "e": ends_at},
            )
            db.commit()
            return True
        except _RETRYABLE as exc:
            last_exc = exc
            try:
                db.rollback()
            except Exception:
                pass
            continue
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
    raise last_exc
