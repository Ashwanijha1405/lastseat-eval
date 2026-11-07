import psycopg.errors

# Namespace for the two-key advisory locks, so they cannot collide with other locks.
_LOCK_NS = 7310
# Bounded number of attempts. Each refused attempt waits for in-flight credits first.
_MAX_ATTEMPTS = 5


def migrate(db) -> None:
    # Defence in depth: balances can never go negative. NOT VALID skips existing rows,
    # but every future insert or update is checked. Skipped if the ALTER is not permitted.
    try:
        db.execute(
            "ALTER TABLE accounts ADD CONSTRAINT accounts_balance_nonneg "
            "CHECK (balance >= 0) NOT VALID"
        )
    except psycopg.Error:
        pass


def _try_once(db, from_id, to_id, amount):
    """Returns True if committed, False if funds were insufficient (nothing changed),
    or None if a deadlock/serialization failure forced a rollback (caller retries)."""
    try:
        db.begin()
        # Declare that a credit to to_id is in progress. Held until this transaction ends.
        db.execute("SELECT pg_advisory_xact_lock_shared(%s, %s)", (_LOCK_NS, to_id))
        # Lock both rows in ascending id order so opposite transfers cannot deadlock.
        balances = {}
        for acc in sorted((from_id, to_id)):
            rows = db.execute(
                "SELECT balance FROM accounts WHERE id = %s FOR UPDATE", (acc,)
            )
            balances[acc] = rows[0][0]
        if balances[from_id] < amount:
            db.rollback()
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
    except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
        db.rollback()
        return None


def _wait_for_incoming(db, account_id):
    """Blocks until every transfer that declared a credit to account_id has ended."""
    try:
        db.begin()
        db.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_LOCK_NS, account_id))
        db.commit()
    except psycopg.errors.DeadlockDetected:
        db.rollback()


def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    for attempt in range(_MAX_ATTEMPTS):
        if _try_once(db, from_id, to_id, amount):
            return True
        if attempt == _MAX_ATTEMPTS - 1:
            break
        # Refused, or lost a race: let in-flight credits to the sender finish, then re-check.
        _wait_for_incoming(db, from_id)
    return False
