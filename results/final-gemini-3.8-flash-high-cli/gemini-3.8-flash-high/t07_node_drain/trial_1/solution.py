from psycopg import errors


def migrate(db) -> None:
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_replicas_node_id ON replicas (node_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_replicas_shard_active ON replicas (shard_id) WHERE active = true"
    )


def drain_node(db, node_id: str) -> bool:
    max_retries = 8
    for attempt in range(max_retries):
        try:
            db.begin(isolation="read committed")

            # 1. Lock the node to serialize concurrent requests for the same node.
            db.execute(
                "SELECT id FROM nodes WHERE id = %s FOR UPDATE",
                (node_id,),
            )

            # 2. Lock all shards associated with this node in ascending order of ID.
            # Locking in strict canonical order prevents deadlocks between concurrent drains.
            db.execute(
                """
                SELECT id FROM shards
                WHERE id IN (
                    SELECT shard_id FROM replicas WHERE node_id = %s
                )
                ORDER BY id
                FOR UPDATE
                """,
                (node_id,),
            )

            # 3. Check if deactivating this node would leave any shard without an active replica.
            # In Read Committed isolation, this query sees the latest committed state of all replicas
            # now that the shard locks are held.
            bad_shards = db.execute(
                """
                SELECT r1.shard_id
                FROM replicas r1
                WHERE r1.node_id = %(node_id)s
                  AND r1.active = true
                  AND NOT EXISTS (
                      SELECT 1
                      FROM replicas r2
                      WHERE r2.shard_id = r1.shard_id
                        AND r2.node_id != %(node_id)s
                        AND r2.active = true
                  )
                LIMIT 1
                """,
                {"node_id": node_id},
            )

            if bad_shards:
                db.commit()
                return False

            # 4. All active replicas on this node can be safely deactivated.
            db.execute(
                """
                UPDATE replicas
                SET active = false
                WHERE node_id = %s
                  AND active = true
                """,
                (node_id,),
            )

            db.commit()
            return True

        except (
            errors.SerializationFailure,
            errors.DeadlockDetected,
            errors.LockNotAvailable,
        ):
            db.rollback()
            if attempt == max_retries - 1:
                raise
        except Exception:
            db.rollback()
            raise

    return False
