import datetime
import psycopg.errors

def migrate(db):
    # Enable GiST operator classes for timestamp ranges
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    
    # Table to track bookings per room per UTC day
    db.execute("""
        CREATE TABLE IF NOT EXISTS room_day_counts (
            room_id int NOT NULL,
            day date NOT NULL,
            booking_count int NOT NULL DEFAULT 0,
            PRIMARY KEY (room_id, day)
        )
    """)
    
    # Initialize counts from existing bookings
    db.execute("""
        INSERT INTO room_day_counts (room_id, day, booking_count)
        SELECT room_id, starts_at::date, count(*)
        FROM bookings
        GROUP BY room_id, starts_at::date
        ON CONFLICT (room_id, day) DO UPDATE SET booking_count = EXCLUDED.booking_count
    """)
    
    # Prevent overlapping bookings for the same room
    db.execute("""
        ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap
        EXCLUDE USING gist (room_id WITH =, tsrange(starts_at, ends_at) WITH &&)
    """)


def _utc_day(dt: datetime.datetime) -> datetime.date:
    """Return the UTC calendar date of a timezone-aware datetime."""
    return dt.astimezone(datetime.timezone.utc).date()


def book(db, room_id: int, starts_at: datetime.datetime, ends_at: datetime.datetime) -> bool:
    day = _utc_day(starts_at)
    for _ in range(3):  # bounded retry loop
        try:
            db.begin("read committed")
            
            # Lock the room-day row and get current count
            rows = db.execute("""
                INSERT INTO room_day_counts (room_id, day, booking_count)
                VALUES (%(room_id)s, %(day)s, 0)
                ON CONFLICT (room_id, day) DO UPDATE SET booking_count = room_day_counts.booking_count
                RETURNING booking_count
            """, {"room_id": room_id, "day": day})
            count = rows[0][0]
            
            if count >= 3:
                db.rollback()
                return False
            
            # Try to insert the booking (exclusion constraint checks overlaps)
            try:
                db.execute("""
                    INSERT INTO bookings (room_id, starts_at, ends_at)
                    VALUES (%(room_id)s, %(starts_at)s, %(ends_at)s)
                """, {"room_id": room_id, "starts_at": starts_at, "ends_at": ends_at})
            except psycopg.errors.ExclusionViolation:
                db.rollback()
                return False
            
            # Increment the day's booking count
            db.execute("""
                UPDATE room_day_counts SET booking_count = booking_count + 1
                WHERE room_id = %(room_id)s AND day = %(day)s
            """, {"room_id": room_id, "day": day})
            
            db.commit()
            return True
        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            db.rollback()
    return False


def cancel(db, booking_id: int) -> bool:
    for _ in range(3):
        try:
            db.begin("read committed")
            
            # Lock the booking row
            rows = db.execute("""
                SELECT room_id, starts_at FROM bookings WHERE id = %(booking_id)s FOR UPDATE
            """, {"booking_id": booking_id})
            if not rows:
                db.rollback()
                return False
            room_id, starts_at = rows[0]
            day = _utc_day(starts_at)
            
            # Lock the room-day row (create if missing, though it should exist)
            db.execute("""
                INSERT INTO room_day_counts (room_id, day, booking_count)
                VALUES (%(room_id)s, %(day)s, 0)
                ON CONFLICT (room_id, day) DO UPDATE SET booking_count = room_day_counts.booking_count
            """, {"room_id": room_id, "day": day})
            
            # Delete the booking
            db.execute("DELETE FROM bookings WHERE id = %(booking_id)s", {"booking_id": booking_id})
            
            # Decrement the day's booking count
            db.execute("""
                UPDATE room_day_counts SET booking_count = booking_count - 1
                WHERE room_id = %(room_id)s AND day = %(day)s
            """, {"room_id": room_id, "day": day})
            
            db.commit()
            return True
        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            db.rollback()
    return False


def reschedule(db, booking_id: int, new_starts_at: datetime.datetime, new_ends_at: datetime.datetime) -> bool:
    for _ in range(3):
        try:
            db.begin("read committed")
            
            # Lock the booking row
            rows = db.execute("""
                SELECT room_id, starts_at FROM bookings WHERE id = %(booking_id)s FOR UPDATE
            """, {"booking_id": booking_id})
            if not rows:
                db.rollback()
                return False
            room_id, old_starts_at = rows[0]
            old_day = _utc_day(old_starts_at)
            new_day = _utc_day(new_starts_at)
            
            if old_day == new_day:
                # Only one day involved
                db.execute("""
                    INSERT INTO room_day_counts (room_id, day, booking_count)
                    VALUES (%(room_id)s, %(day)s, 0)
                    ON CONFLICT (room_id, day) DO UPDATE SET booking_count = room_day_counts.booking_count
                """, {"room_id": room_id, "day": old_day})
                
                try:
                    db.execute("""
                        UPDATE bookings SET starts_at = %(new_starts_at)s, ends_at = %(new_ends_at)s
                        WHERE id = %(booking_id)s
                    """, {"booking_id": booking_id, "new_starts_at": new_starts_at, "new_ends_at": new_ends_at})
                except psycopg.errors.ExclusionViolation:
                    db.rollback()
                    return False
                
                db.commit()
                return True
            else:
                # Two different days – lock both in a consistent order (by day)
                days = sorted([old_day, new_day])
                counts = {}
                for day in days:
                    rows = db.execute("""
                        INSERT INTO room_day_counts (room_id, day, booking_count)
                        VALUES (%(room_id)s, %(day)s, 0)
                        ON CONFLICT (room_id, day) DO UPDATE SET booking_count = room_day_counts.booking_count
                        RETURNING booking_count
                    """, {"room_id": room_id, "day": day})
                    counts[day] = rows[0][0]
                
                # The new day must have room for this booking (old day already counts it)
                if counts[new_day] >= 3:
                    db.rollback()
                    return False
                
                # Attempt the move
                try:
                    db.execute("""
                        UPDATE bookings SET starts_at = %(new_starts_at)s, ends_at = %(new_ends_at)s
                        WHERE id = %(booking_id)s
                    """, {"booking_id": booking_id, "new_starts_at": new_starts_at, "new_ends_at": new_ends_at})
                except psycopg.errors.ExclusionViolation:
                    db.rollback()
                    return False
                
                # Adjust the daily counts
                db.execute("""
                    UPDATE room_day_counts SET booking_count = booking_count - 1
                    WHERE room_id = %(room_id)s AND day = %(day)s
                """, {"room_id": room_id, "day": old_day})
                db.execute("""
                    UPDATE room_day_counts SET booking_count = booking_count + 1
                    WHERE room_id = %(room_id)s AND day = %(day)s
                """, {"room_id": room_id, "day": new_day})
                
                db.commit()
                return True
        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            db.rollback()
    return False
