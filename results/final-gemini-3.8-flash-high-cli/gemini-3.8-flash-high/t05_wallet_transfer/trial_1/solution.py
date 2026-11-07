from __future__ import annotations

from psycopg.errors import DeadlockDetected, SerializationFailure


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    first_id = min(from_id, to_id)
    second_id = max(from_id, to_id)

    for _ in range(10):
        try:
            db.begin()

            # Lock the lower account ID first to prevent deadlocks across concurrent transfers
            r1 = db.execute(
                "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                (first_id,),
            )
            if first_id == from_id and r1[0][0] < amount:
                db.rollback()
                return False

            # Lock the higher account ID
            r2 = db.execute(
                "SELECT balance FROM accounts WHERE id = %s FOR UPDATE",
                (second_id,),
            )

            from_balance = r1[0][0] if from_id == first_id else r2[0][0]
            if from_balance < amount:
                db.rollback()
                return False

            # Apply the balance adjustments atomically
            db.execute(
                "UPDATE accounts "
                "SET balance = balance + CASE WHEN id = %s THEN %s ELSE %s END "
                "WHERE id IN (%s, %s)",
                (to_id, amount, -amount, from_id, to_id),
            )
            db.commit()
            return True

        except (DeadlockDetected, SerializationFailure):
            try:
                db.rollback()
            except Exception:
                pass
            continue

    return False
