"""Locks its own row with FOR UPDATE, then counts and updates.

The lock protects the row being written, but the danger is the colleague's
row being read. The two requests lock different rows, never wait for each
other, and both go off call.

EXPECT: safety
"""


def go_off_call(db, doctor_id: int) -> bool:
    db.begin()
    [(shift_id,)] = db.execute("SELECT shift_id FROM doctors WHERE id = %s FOR UPDATE", (doctor_id,))
    [(n,)] = db.execute("SELECT count(*) FROM doctors WHERE shift_id = %s AND on_call", (shift_id,))
    if n < 2:
        db.rollback()
        return False
    db.execute("UPDATE doctors SET on_call = false WHERE id = %s", (doctor_id,))
    db.commit()
    return True
