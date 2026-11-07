import psycopg.errors
from collections import defaultdict

def migrate(db) -> None:
    # Add indexes to speed up the queries used in drain_node
    db.execute("""
        CREATE INDEX IF NOT EXISTS replicas_node_active_idx
        ON replicas (node_id, active)
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS replicas_shard_active_idx
        ON replicas (shard_id, active)
    """)
    db.commit()

def drain_node(db, node_id: str) -> bool:
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin(isolation="repeatable read")

            # Lock all active replicas for shards where this node has an active replica.
            # The ORDER BY ensures a global lock order to avoid deadlocks.
            sql = """
                SELECT r.shard_id, r.node_id
                FROM replicas r
                WHERE r.shard_id IN (
                    SELECT shard_id FROM replicas
                    WHERE node_id = %(node_id)s AND active = true
                )
                AND r.active = true
                FOR UPDATE ORDER BY r.shard_id, r.node_id
            """
            rows = db.execute(sql, {"node_id": node_id})

            # Group active replicas by shard
            shard_to_nodes = defaultdict(set)
            for shard_id, nid in rows:
                shard_to_nodes[shard_id].add(nid)

            # Check the drain condition: for each shard, there must be another active node.
            can_drain = True
            for nodes in shard_to_nodes.values():
                if nodes == {node_id}:
                    can_drain = False
                    break

            if not can_drain:
                db.rollback()
                return False

            # Deactivate all replicas on this node
            db.execute(
                "UPDATE replicas SET active = false WHERE node_id = %(node_id)s",
                {"node_id": node_id}
            )
            db.commit()
            return True

        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            db.rollback()
            # Retry on serialization failure or deadlock
            continue
        except Exception:
            db.rollback()
            # For any other error, retry as well (bounded by max_attempts)
            continue

    # Should not happen under normal contention, but return False if retries exhausted
    return False
