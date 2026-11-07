import psycopg.errors
from psycopg.errors import SerializationFailure, DeadlockDetected

def drain_node(db, node_id: str) -> bool:
    """
    Drains a storage node by deactivating all its replicas if every shard that
    has an active replica on this node also has at least one active replica on
    another node. Returns True on success, False if draining would leave a shard
    without any active replica.
    """
    max_attempts = 10
    for attempt in range(max_attempts):
        db.begin(isolation="repeatable read")
        try:
            # Lock all active replicas belonging to shards where this node has an active replica.
            # The ORDER BY ensures a consistent lock order across concurrent transactions.
            sql = """
                WITH our_shards AS (
                    SELECT shard_id
                    FROM replicas
                    WHERE node_id = %s AND active = true
                )
                SELECT r.shard_id, r.node_id
                FROM replicas r
                JOIN our_shards o ON r.shard_id = o.shard_id
                WHERE r.active = true
                FOR UPDATE OF r ORDER BY r.shard_id, r.node_id
            """
            rows = db.execute(sql, (node_id,))

            # Determine which shards this node serves actively and count other active replicas per shard.
            our_shards = set()
            other_active_count = {}
            for shard_id, node_id_row in rows:
                if node_id_row == node_id:
                    our_shards.add(shard_id)
                else:
                    other_active_count[shard_id] = other_active_count.get(shard_id, 0) + 1

            # If any of our shards would lose its last active replica, abort.
            for shard_id in our_shards:
                if other_active_count.get(shard_id, 0) == 0:
                    db.rollback()
                    return False

            # All checks passed: deactivate every active replica on this node.
            update_sql = "UPDATE replicas SET active = false WHERE node_id = %s AND active = true"
            db.execute(update_sql, (node_id,))
            db.commit()
            return True

        except (SerializationFailure, DeadlockDetected):
            db.rollback()
            # Retry on serialization failure or deadlock; give up after max_attempts.
            if attempt == max_attempts - 1:
                return False
        except Exception:
            db.rollback()
            raise

    return False
