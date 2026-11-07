import psycopg.errors


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

        # Serialize all requests for this shift.
        db.execute(
            "SELECT id FROM shifts WHERE id = %(s)s FOR NO KEY UPDATE",
            {"s": shift_id},
        )

        # Fresh snapshot per statement in READ COMMITTED: sees prior commits.
        cnt = db.execute(
            "SELECT count(*) FROM doctors "
            "WHERE shift_id = %(s)s AND on_call AND id <> %(d)s",
            {"s": shift_id, "d": doctor_id},
        )[0][0]

        if cnt >= 1:
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
