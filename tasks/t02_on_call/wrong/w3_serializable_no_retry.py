"""Check-then-update under SERIALIZABLE, without retrying.

Safe: Postgres notices that each transaction read a row the other one wrote
and aborts one of them with SerializationFailure (40001). But the aborted
request reaches the caller as an error instead of being retried, so valid
concurrent requests fail.

EXPECT: liveness
"""


def go_off_call(db, doctor_id: int) -> bool:
    db.begin("serializable")
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
