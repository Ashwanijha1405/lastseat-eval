def go_off_call(db, doctor_id: int) -> bool:
    db.begin("read committed")
    try:
        rows = db.execute(
            "SELECT shift_id FROM doctors WHERE id = %(d)s",
            {"d": doctor_id},
        )
        if not rows:
            db.rollback()
            return False
        shift_id = rows[0][0]

        # Serialize all requests touching the same shift.
        db.execute(
            "SELECT id FROM shifts WHERE id = %(s)s FOR UPDATE",
            {"s": shift_id},
        )

        # Fresh snapshot (read committed) after the lock is acquired.
        others = db.execute(
            "SELECT count(*) FROM doctors "
            "WHERE shift_id = %(s)s AND on_call AND id <> %(d)s",
            {"s": shift_id, "d": doctor_id},
        )[0][0]

        if others >= 1:
            db.execute(
                "UPDATE doctors SET on_call = false WHERE id = %(d)s",
                {"d": doctor_id},
            )
            db.commit()
            return True

        db.rollback()
        return False
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
