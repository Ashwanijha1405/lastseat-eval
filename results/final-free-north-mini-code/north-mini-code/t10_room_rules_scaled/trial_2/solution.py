import psycopg.errors

MAX_ATTEMPTS = 5

def migrate(db):
    # Add the btree_gist extension for exclusion constraints
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    # Prevent overlapping bookings in the same room
    db.execute("""
        ALTER TABLE bookings
        ADD CONSTRAINT bookings_exclude
        EXCLUDE USING GIST (room_id WITH =, tsrange(starts_at, ends_at, '[)'));
    """)
    # Limit to at most 3 bookings per room per UTC calendar day
    db.execute("""
        ALTER TABLE bookings
        ADD CONSTRAINT bookings_capacity_check
        CHECK (
            (
                SELECT count(*) FROM bookings b
                WHERE b.room_id = NEW.room_id
                AND date(b.starts_at) = date(NEW.starts_at)
            ) <= 3
        );
    """)

def book(db, room_id, starts_at, ends_at):
    for attempt in range(MAX_ATTEMPTS):
        try:
            db.begin(isolation='serializable')
            db.execute(
                "INSERT INTO bookings (room_id, starts_at, ends_at) VALUES (%s, %s, %s)",
                (room_id, starts_at, ends_at)
            )
            db.commit()
            return True
        except psycopg.errors.Error:
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                return False
    return False

def reschedule(db, booking_id, new_starts_at, new_ends_at):
    for attempt in range(MAX_ATTEMPTS):
        try:
            db.begin(isolation='serializable')
            rows = db.execute(
                "SELECT room_id, starts_at, ends_at FROM bookings WHERE id = %s FOR UPDATE",
                (booking_id,)
            )
            if not rows:
                db.rollback()
                return False
            db.execute(
                "UPDATE bookings SET starts_at = %s, ends_at = %s WHERE id = %s",
                (new_starts_at, new_ends_at, booking_id)
            )
            db.commit()
            return True
        except psycopg.errors.Error:
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                return False
    return False

def cancel(db, booking_id):
    for attempt in range(MAX_ATTEMPTS):
        try:
            db.begin(isolation='serializable')
            rows = db.execute(
                "SELECT * FROM bookings WHERE id = %s FOR UPDATE",
                (booking_id,)
            )
            if not rows:
                db.rollback()
                return False
            db.execute(
                "DELETE FROM bookings WHERE id = %s",
                (booking_id,)
            )
            db.commit()
            return True
        except psycopg.errors.Error:
            db.rollback()
            if attempt == MAX_ATTEMPTS - 1:
                return False
    return False
