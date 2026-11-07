import psycopg.errors


def migrate(db) -> None:
    # Optional index to speed up the lookup of active replicas for a node.
    db.execute(
        "CREATE INDEX IF NOT EXISTS replicas_node_active_idx ON replicas (node_id, active)"
    )


def drain_node(db, node_id: str) -> bool:
    max_attempts = 3
    for _ in range(max_attempts):
        try:
            db.begin()  # default isolation level: read committed

            # Lock all shards where this node currently has an active replica.
            # Order by shard_id to avoid deadlocks with concurrent drains.
            rows = db.execute(
                """
                SELECT s.id
                FROM shards s
                JOIN replicas r ON s.id = r.shard_id
                WHERE r.node_id = %s AND r.active = true
                ORDER BY s.id
                FOR UPDATE
                """,
                (node_id,),
            )
            shard_ids = [row[0] for row in rows]

            # If the node has no active replicas, draining is trivially successful.
            if not shard_ids:
                db.commit()
                return True

            # Check whether any of these shards would be left without an active replica
            # on a *different* node.
            rows = db.execute(
                """
                SELECT s.shard_id
                FROM unnest(%s) AS s(shard_id)
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM replicas r
                    WHERE r.shard_id = s.shard_id
                      AND r.active = true
                      AND r.node_id != %s
                )
                """,
                (shard_ids, node_id),
            )

            if rows:
                # At least one shard would lose its last active replica.
                db.rollback()
                return False

            # All checks passed – deactivate every active replica on this node.
            db.execute(
                """
                UPDATE replicas
                SET active = false
                WHERE node_id = %s AND active = true
                """,
                (node_id,),
            )

            db.commit()
            return True

        except psycopg.errors.DeadlockDetected:
            db.rollback()
            continue
        except psycopg.errors.SerializationFailure:
            db.rollback()
            continue
        except psycopg.Error:
            db.rollback()
            return False
        except Exception:
            db.rollback()
            return False

    # Retries exhausted (only possible for deadlock/serialization errors).
    return False
