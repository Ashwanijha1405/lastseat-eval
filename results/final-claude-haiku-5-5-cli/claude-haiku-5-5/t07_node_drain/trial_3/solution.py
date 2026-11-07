from psycopg.errors import DeadlockDetected, SerializationFailure


def drain_node(db, node_id: str) -> bool:
    # Lock every shard that has a replica on this node, in ascending id order.
    # Any drain that could change one of these shards' active flags must hold
    # the same shard lock, so the check below sees a settled state. Consistent
    # lock ordering prevents deadlocks between concurrent drains.
    for _ in range(10):
        try:
            db.begin()
            db.execute(
                "SELECT s.id FROM shards s "
                "WHERE s.id IN (SELECT r.shard_id FROM replicas r WHERE r.node_id = %s) "
                "ORDER BY s.id FOR UPDATE",
                (node_id,),
            )
            # Is there a shard where this node is active and no other node is active?
            rows = db.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM replicas r "
                "  WHERE r.node_id = %s AND r.active "
                "  AND NOT EXISTS ("
                "    SELECT 1 FROM replicas o "
                "    WHERE o.shard_id = r.shard_id "
                "      AND o.node_id <> %s "
                "      AND o.active"
                "  )"
                ")",
                (node_id, node_id),
            )
            if rows[0][0]:
                db.rollback()
                return False

            db.execute(
                "UPDATE replicas SET active = false WHERE node_id = %s",
                (node_id,),
            )
            db.commit()
            return True
        except (SerializationFailure, DeadlockDetected):
            db.rollback()
    return False
