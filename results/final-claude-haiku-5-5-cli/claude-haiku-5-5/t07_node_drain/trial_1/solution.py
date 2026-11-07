from psycopg import errors


def drain_node(db, node_id: str) -> bool:
    # Each attempt uses at most 5 db calls; 10 attempts stays under the 60 limit.
    for _ in range(10):
        try:
            db.begin()  # read committed (default)

            # Lock every shard where this node is currently active, in ascending
            # id order so concurrent drains acquire locks in the same order.
            # Any other drain that could change a replica of one of these shards
            # must hold this lock first, so the check below is stable.
            db.execute(
                """
                SELECT s.id
                FROM shards s
                WHERE s.id IN (
                    SELECT r.shard_id
                    FROM replicas r
                    WHERE r.node_id = %s AND r.active
                )
                ORDER BY s.id
                FOR UPDATE OF s
                """,
                (node_id,),
            )

            # New statement => new snapshot under read committed, so this sees
            # every drain that committed before we acquired the locks.
            blocking = db.execute(
                """
                SELECT 1
                FROM replicas r
                WHERE r.node_id = %s
                  AND r.active
                  AND NOT EXISTS (
                      SELECT 1
                      FROM replicas o
                      WHERE o.shard_id = r.shard_id
                        AND o.node_id <> r.node_id
                        AND o.active
                  )
                LIMIT 1
                """,
                (node_id,),
            )
            if blocking:
                db.rollback()
                return False

            db.execute(
                "UPDATE replicas SET active = false WHERE node_id = %s AND active",
                (node_id,),
            )
            db.commit()
            return True
        except errors.DeadlockDetected:
            db.rollback()
            continue

    # Not expected to be reached: ordered shard locking prevents deadlocks, and
    # no other error is retried. Report "not drained" rather than raising.
    return False
