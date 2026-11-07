import psycopg.errors
from psycopg.errors import DeadlockDetected, SerializationFailure


def drain_node(db, node_id: str) -> bool:
    for _ in range(5):
        try:
            db.begin("read committed")

            # Serialize drains that share a shard by locking the shard rows
            # in a consistent order (ascending id), so there are no deadlocks.
            # A drain that conflicts waits for the other one and then sees its result.
            db.execute(
                """
                SELECT id FROM shards
                WHERE id IN (SELECT shard_id FROM replicas
                             WHERE node_id = %(n)s AND active)
                ORDER BY id
                FOR UPDATE
                """,
                {"n": node_id},
            )

            # New statement after locks are held: sees every committed drain.
            rows = db.execute(
                """
                SELECT 1
                FROM replicas r
                WHERE r.node_id = %(n)s AND r.active
                  AND NOT EXISTS (
                      SELECT 1 FROM replicas o
                      WHERE o.shard_id = r.shard_id
                        AND o.node_id <> %(n)s
                        AND o.active
                  )
                LIMIT 1
                """,
                {"n": node_id},
            )
            if rows:
                db.rollback()
                return False

            db.execute(
                "UPDATE replicas SET active = false WHERE node_id = %(n)s AND active",
                {"n": node_id},
            )
            db.commit()
            return True
        except (DeadlockDetected, SerializationFailure):
            db.rollback()
            continue
    return False
