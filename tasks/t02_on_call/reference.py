"""Reference: lock every on-call row of the shift before counting.

A concurrent request for the same shift runs the same locking query and waits
for the first one to commit. Under READ COMMITTED it then re-reads the newest
version of each row it waited for and re-checks `on_call`, so a colleague who
just went off call drops out of its result. Both requests lock rows in the
same order, so they cannot deadlock.
"""


def go_off_call(db, doctor_id: int) -> bool:
    db.begin()
    rows = db.execute(
        "SELECT id FROM doctors"
        " WHERE shift_id = (SELECT shift_id FROM doctors WHERE id = %(id)s) AND on_call"
        " FOR UPDATE",
        {"id": doctor_id},
    )
    on_call = {r[0] for r in rows}
    if doctor_id not in on_call or len(on_call) < 2:
        db.rollback()
        return False
    db.execute("UPDATE doctors SET on_call = false WHERE id = %s", (doctor_id,))
    db.commit()
    return True
