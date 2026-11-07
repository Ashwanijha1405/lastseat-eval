import psycopg.errors

def drain_node(db, node_id: str) -> bool:
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            db.begin()
            # Lock all shards that currently have an active replica on this node.
            # The ORDER BY ensures a consistent lock order to avoid deadlocks.
            db.execute(
                "SELECT id FROM shards "
                "WHERE id IN (SELECT shard_id FROM replicas WHERE node_id = %s AND active = true) "
                "ORDER BY id FOR UPDATE",
                (node_id,)
            )
            # Check whether any of those shards would be left without an active replica.
            rows = db.execute(
                "SELECT 1 FROM replicas r "
                "WHERE r.node_id = %s AND r.active = true "
                "AND NOT EXISTS ("
                "    SELECT 1 FROM replicas r2 "
                "    WHERE r2.shard_id = r.shard_id "
                "      AND r2.node_id != r.node_id "
                "      AND r2.active = true"
                ") LIMIT 1",
                (node_id,)
            )
            if rows:
                db.rollback()
                return False
            # All shards have at least one other active replica – deactivate this node's replicas.
            db.execute(
                "UPDATE replicas SET active = false WHERE node_id = %s AND active = true",
                (node_id,)
            )
            db.commit()
            return True
        except psycopg.errors.DeadlockDetected:
            db.rollback()
            continue
        except psycopg.errors.Error:
            db.rollback()
            return False
    return False
