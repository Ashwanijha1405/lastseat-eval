import psycopg.errors as errors


def migrate(db) -> None:
    db.execute("CREATE INDEX IF NOT EXISTS replicas_node_id_idx ON replicas (node_id, shard_id)")


def drain_node(db, node_id: str) -> bool:
    attempts = 8
    for attempt in range(attempts):
        try:
            db.begin("read committed")
            # Lock every shard this node holds a replica of, in a global
            # (ascending id) order so concurrent drains never deadlock.
            db.execute(
                """
                SELECT s.id
                FROM shards s
                WHERE s.id IN (SELECT r.shard_id FROM replicas r WHERE r.node_id = %(n)s)
                ORDER BY s.id
                FOR UPDATE OF s
                """,
                {"n": node_id},
            )
            # Fresh snapshot (READ COMMITTED): sees all drains that held these locks before us.
            rows = db.execute(
                """
                SELECT 1
                FROM replicas r
                WHERE r.node_id = %(n)s
                  AND r.active
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
        except (errors.DeadlockDetected, errors.SerializationFailure, errors.LockNotAvailable):
            try:
                db.rollback()
            except Exception:
                pass
            if attempt == attempts - 1:
                raise
    return False
