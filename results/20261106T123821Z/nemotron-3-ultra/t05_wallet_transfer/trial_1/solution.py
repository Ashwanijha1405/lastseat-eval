import psycopg.errors

TRANSFER_SQL = """
WITH locked AS (
    SELECT id, balance FROM accounts WHERE id IN (%(from_id)s, %(to_id)s) ORDER BY id FOR UPDATE
), debit AS (
    UPDATE accounts SET balance = balance - %(amount)s
    WHERE id = %(from_id)s
      AND (SELECT balance FROM locked WHERE id = %(from_id)s) >= %(amount)s
    RETURNING 1
)
UPDATE accounts SET balance = balance + %(amount)s
WHERE id = %(to_id)s
  AND EXISTS (SELECT 1 FROM debit)
RETURNING 1;
"""

def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    max_attempts = 20
    params = {'from_id': from_id, 'to_id': to_id, 'amount': amount}
    for _ in range(max_attempts):
        db.begin()
        try:
            rows = db.execute(TRANSFER_SQL, params)
            if rows:
                db.commit()
                return True
            else:
                db.rollback()
        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            db.rollback()
        except psycopg.Error:
            db.rollback()
            return False
    return False

def migrate(db) -> None:
    pass
