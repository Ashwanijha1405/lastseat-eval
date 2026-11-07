from psycopg import errors

_RETRYABLE = (errors.SerializationFailure, errors.DeadlockDetected)
# Worst case per attempt: begin, 2 locking selects, 2 updates, commit, plus a
# rollback on failure = 7 calls. 8 attempts * 7 = 56, which is within the 60 limit.
_MAX_ATTEMPTS = 8


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    # Always lock the lower id first. Every transfer uses the same global lock
    # order, so two transfers can never wait on each other in a cycle.
    first, second = sorted((from_id, to_id))

    last_error = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            db.begin()

            balances = {}
            for account_id in (first, second):
                rows = db.execute(
                    "SELECT id, balance FROM accounts WHERE id = %s FOR UPDATE",
                    (account_id,),
                )
                # FOR UPDATE returns the latest committed version of the row
                # after waiting for any concurrent transaction to finish.
                balances[account_id] = rows[0][1]

            if balances[from_id] < amount:
                db.commit()  # nothing was changed
                return False

            db.execute(
                "UPDATE accounts SET balance = balance - %s WHERE id = %s",
                (amount, from_id),
            )
            db.execute(
                "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                (amount, to_id),
            )
            db.commit()
            return True

        except _RETRYABLE as exc:
            last_error = exc
            db.rollback()
        except Exception:
            db.rollback()
            raise

    # Only reached if deadlocks or serialization failures persisted through
    # every attempt. Surface that rather than reporting a refusal.
    raise last_error
