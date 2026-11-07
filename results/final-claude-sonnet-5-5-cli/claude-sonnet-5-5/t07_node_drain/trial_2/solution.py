import psycopg
import psycopg.errors


def drain_node(db, node_id: str) -> bool:
    for _ in range(5):
        try:
            db.begin("read committed")
            # Lock every shard this node has a replica of, in a fixed order.
            db.execute(
                """
                SELECT s.id
                FROM shards s
                JOIN replicas r ON r.shard_id = s.id
                WHERE r.node_id = %(n)s
                ORDER BY s.id
                FOR UPDATE OF s
                """,
                {"n": node_id},
            )
            # Fresh snapshot (read committed) after locks are held.
            bad = db.execute(
                """
                SELECT 1
                FROM replicas r
                WHERE r.node_id = %(n)s
                  AND r.active
                  AND NOT EXISTS (
                      SELECT 1 FROM replicas o
                      WHERE o.shard_id = r.shard_id
                        AND o.node_id <> r.node_id
                        AND o.active
                  )
                LIMIT 1
                """,
                {"n": node_id},
            )
            if bad:
                db.rollback()
                return False
            db.execute(
                "UPDATE replicas SET active = false WHERE node_id = %(n)s AND active",
                {"n": node_id},
            )
            db.commit()
            return True
        except (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure):
            db.rollback()
            continue
    return False
