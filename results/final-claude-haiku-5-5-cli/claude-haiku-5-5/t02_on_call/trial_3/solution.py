def go_off_call(db, doctor_id: int) -> bool:
    db.begin()  # "read committed"
    try:
        rows = db.execute(
            "SELECT shift_id FROM doctors WHERE id = %s",
            (doctor_id,),
        )
        if not rows:
            db.rollback()
            return False
        shift_id = rows[0][0]

        # Serialise off-call requests for this shift. Each request takes this
        # lock before reading or changing any doctor in the shift, so the count
        # below runs after every earlier request in the shift has committed.
        db.execute(
            "SELECT id FROM shifts WHERE id = %s FOR UPDATE",
            (shift_id,),
        )

        rows = db.execute(
            "SELECT count(*) FROM doctors "
            "WHERE shift_id = %s AND on_call AND id <> %s",
            (shift_id, doctor_id),
        )
        others_on_call = rows[0][0]

        if others_on_call <= 0:
            # This doctor is the only one on call: change nothing.
            db.commit()
            return False

        db.execute(
            "UPDATE doctors SET on_call = false WHERE id = %s",
            (doctor_id,),
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
