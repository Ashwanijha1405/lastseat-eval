from psycopg import errors

_MAX_ATTEMPTS = 10


def drain_node(db, node_id: str) -> bool:
    for _ in range(_MAX_ATTEMPTS):
        try:
            db.begin()

            # Lock every shard this node has a replica of, in ascending id order.
            # Any drain that changes replicas of one of these shards must hold the
            # same shard lock, so the check below cannot race with another drain.
            # The fixed lock order prevents deadlocks between drains.
            db.execute(
                """
                SELECT s.id
                FROM shards s
                WHERE s.id IN (SELECT r.shard_id FROM replicas r WHERE r.node_id = %s)
                ORDER BY s.id
                FOR UPDATE OF s
                """,
                (node_id,),
            )

            # Under the shard locks, this statement sees the committed state of
            # every shard this node touches. Is there any shard where this node is
            # active and no other node is active?
            blocked = db.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM replicas mine
                    WHERE mine.node_id = %s
                      AND mine.active
                      AND NOT EXISTS (
                          SELECT 1
                          FROM replicas other
                          WHERE other.shard_id = mine.shard_id
                            AND other.node_id <> %s
                            AND other.active
                      )
                )
                """,
                (node_id, node_id),
            )[0][0]

            if blocked:
                db.rollback()
                return False

            db.execute(
                "UPDATE replicas SET active = false WHERE node_id = %s AND active",
                (node_id,),
            )
            db.commit()
            return True

        except (errors.DeadlockDetected, errors.SerializationFailure):
            db.rollback()
            continue

    # Retries should not be exhausted with ordered locking; raise rather than
    # return a answer that might be wrong.
    raise RuntimeError("drain_node: retry limit exceeded")
