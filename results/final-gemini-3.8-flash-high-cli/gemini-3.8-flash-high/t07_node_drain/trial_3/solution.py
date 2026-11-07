from __future__ import annotations

from psycopg import errors

# Unique 64-bit advisory lock key to serialize drain evaluations
_DRAIN_LOCK_ID = 6001150428613362770


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_replicas_node_active "
        "ON replicas (node_id, shard_id) WHERE active = true"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_replicas_shard_active "
        "ON replicas (shard_id, node_id) WHERE active = true"
    )


def drain_node(db, node_id: str) -> bool:
    for _ in range(12):
        try:
            db.begin()
            db.execute(
                "SELECT pg_advisory_xact_lock(%(lock_id)s)",
                {"lock_id": _DRAIN_LOCK_ID},
            )

            # Check if any shard with an active replica on this node
            # would be left with no active replica on any other node.
            blocked = db.execute(
                """
                SELECT 1
                FROM replicas cs
                WHERE cs.node_id = %(node_id)s
                  AND cs.active = true
                  AND NOT EXISTS (
                      SELECT 1
                      FROM replicas r
                      WHERE r.shard_id = cs.shard_id
                        AND r.node_id != %(node_id)s
                        AND r.active = true
                  )
                LIMIT 1
                """,
                {"node_id": node_id},
            )

            if blocked:
                db.commit()
                return False

            db.execute(
                """
                UPDATE replicas
                SET active = false
                WHERE node_id = %(node_id)s
                  AND active = true
                """,
                {"node_id": node_id},
            )
            db.commit()
            return True
        except (errors.SerializationFailure, errors.DeadlockDetected):
            try:
                db.rollback()
            except Exception:
                pass
            continue
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise

    return False
