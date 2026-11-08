from datetime import datetime
from psycopg.errors import ExclusionViolation

def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    db.begin()
    try:
        db.execute(
            """
            INSERT INTO bookings (room_id, starts_at, ends_at)
            VALUES (%(room_id)s, %(starts_at)s, %(ends_at)s)
            """,
            {"room_id": room_id, "starts_at": starts_at, "ends_at": ends_at}
        )
        db.commit()
        return True
    except ExclusionViolation:
        db.rollback()
        return False

def migrate(db):
    # Ensure the btree_gist extension is available for GIST exclusion constraints
    db.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    # Add an exclusion constraint that prevents overlapping bookings per room
    db.execute("""
    ALTER TABLE bookings
    ADD CONSTRAINT bookings_nooverlap
    EXCLUDE USING GIST (room_id WITH =, tsrange(starts_at, ends_at) WITH &&);
    """)
