import psycopg.errors as pg_errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS replicas_node_shard_idx "
        "ON replicas (node_id, shard_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS replicas_shard_active_idx "
        "ON replicas (shard_id, node_id) WHERE active"
    )


_LOCK_SQL = (
    "SELECT s.id FROM shards s "
    "WHERE s.id IN (SELECT r.shard_id FROM replicas r WHERE r.node_id = %(n)s) "
    "ORDER BY s.id "
    "FOR NO KEY UPDATE OF s"
)

_CHECK_SQL = (
    "SELECT 1 FROM replicas r "
    "WHERE r.node_id = %(n)s AND r.active "
    "AND NOT EXISTS ("
    "  SELECT 1 FROM replicas o "
    "  WHERE o.shard_id = r.shard_id AND o.node_id <> r.node_id AND o.active"
    ") LIMIT 1"
)

_UPDATE_SQL = "UPDATE replicas SET active = false WHERE node_id = %(n)s AND active"


def drain_node(db, node_id: str) -> bool:
    params = {"n": node_id}
    last_exc = None
    for _ in range(10):  # each attempt uses at most 5 db calls
        try:
            db.begin("read committed")
            # Serialize against any concurrent drain touching the same shards,
            # acquiring locks in a global order (shard id) to avoid deadlocks.
            db.execute(_LOCK_SQL, params)
            # Fresh snapshot (READ COMMITTED) taken after locks are held.
            if db.execute(_CHECK_SQL, params):
                db.rollback()
                return False
            db.execute(_UPDATE_SQL, params)
            db.commit()
            return True
        except (
            pg_errors.DeadlockDetected,
            pg_errors.SerializationFailure,
            pg_errors.LockNotAvailable,
        ) as exc:
            last_exc = exc
            try:
                db.rollback()
            except Exception:
                pass
            continue
    raise last_exc
