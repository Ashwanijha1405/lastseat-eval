import psycopg.errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS replicas_node_active_idx "
        "ON replicas (node_id, shard_id) WHERE active"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS replicas_shard_active_idx "
        "ON replicas (shard_id, node_id) WHERE active"
    )


_RETRYABLE = (
    psycopg.errors.DeadlockDetected,
    psycopg.errors.SerializationFailure,
    psycopg.errors.LockNotAvailable,
)


def drain_node(db, node_id: str) -> bool:
    for _ in range(10):
        try:
            db.begin("read committed")

            # Lock every shard that currently has an active replica on this node,
            # in a consistent order to avoid deadlocks between concurrent drains.
            db.execute(
                "SELECT s.id FROM shards s "
                "WHERE s.id IN ("
                "  SELECT r.shard_id FROM replicas r "
                "  WHERE r.node_id = %(n)s AND r.active"
                ") "
                "ORDER BY s.id FOR UPDATE",
                {"n": node_id},
            )

            # Fresh snapshot (read committed): see drains that committed while we waited.
            blocking = db.execute(
                "SELECT 1 FROM replicas r "
                "WHERE r.node_id = %(n)s AND r.active "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM replicas o "
                "  WHERE o.shard_id = r.shard_id "
                "    AND o.node_id <> r.node_id "
                "    AND o.active"
                ") LIMIT 1",
                {"n": node_id},
            )
            if blocking:
                db.rollback()
                return False

            db.execute(
                "UPDATE replicas SET active = false "
                "WHERE node_id = %(n)s AND active",
                {"n": node_id},
            )
            db.commit()
            return True
        except _RETRYABLE:
            try:
                db.rollback()
            except Exception:
                pass
            continue
    return False
