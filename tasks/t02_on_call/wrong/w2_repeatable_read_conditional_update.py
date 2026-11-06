"""One conditional UPDATE under REPEATABLE READ.

REPEATABLE READ gives each transaction a fixed snapshot, and both snapshots
say two doctors are on call. It only raises an error when two transactions
write the same row; here they write different rows, so both commit.

EXPECT: safety
"""


def go_off_call(db, doctor_id: int) -> bool:
    db.begin("repeatable read")
    rows = db.execute(
        "UPDATE doctors SET on_call = false"
        " WHERE id = %(id)s AND (SELECT count(*) FROM doctors o"
        "   WHERE o.shift_id = doctors.shift_id AND o.on_call) >= 2"
        " RETURNING id",
        {"id": doctor_id},
    )
    db.commit()
    return bool(rows)
