"""Counts on-call colleagues with a plain SELECT, then updates its own row.

Both requests count 2, and each updates a different row, so neither UPDATE
waits for the other. Both commit and the shift is left with nobody on call.

EXPECT: safety
"""


def go_off_call(db, doctor_id: int) -> bool:
    db.begin()
    [(n,)] = db.execute(
        "SELECT count(*) FROM doctors"
        " WHERE shift_id = (SELECT shift_id FROM doctors WHERE id = %(id)s) AND on_call",
        {"id": doctor_id},
    )
    if n < 2:
        db.rollback()
        return False
    db.execute("UPDATE doctors SET on_call = false WHERE id = %s", (doctor_id,))
    db.commit()
    return True
