from psycopg import errors
from typing import List, Tuple

def migrate(db) -> None:
    # Create an index on (shard_id, node_id) to enforce a global lock order
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_replicas_shard_node
        ON replicas (shard_id, node_id)
        """
    )

def drain_node(db, node_id: str) -> bool:
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin(isolation="serializable")

            # Step 1: find shards where this node currently has an active replica
            node_rows = db.execute(
                "SELECT shard_id FROM replicas WHERE node_id = %s AND active = true",
                (node_id,)
            )
            shard_ids = [row[0] for row in node_rows]

            # If the node has no active replicas, draining is trivially successful
            if not shard_ids:
                db.commit()
                return True

            # Step 2: lock all relevant rows (own + backup) in global order (shard_id, node_id)
            locked = db.execute(
                """
                SELECT * FROM replicas
                WHERE (node_id = %s AND active = true)
                   OR (shard_id IN %s AND node_id != %s AND active = true)
                ORDER BY shard_id, node_id
                FOR UPDATE
                """,
                (node_id, tuple(shard_ids), node_id)
            )

            # Determine which shards have at least one other active replica on a different node
            backup_shards = {
                row[0] for row in locked if row[1] != node_id
            }

            # Condition: every shard we need to protect must have a backup
            if not backup_shards.issuperset(shard_ids):
                db.rollback()
                return False

            # Step 3: deactivate the node's active replicas
            db.execute(
                "UPDATE replicas SET active = false WHERE node_id = %s AND active = true",
                (node_id,)
            )

            db.commit()
            return True

        except errors.Error as e:
            # On any database error (most likely a concurrency issue), rollback and retry
            db.rollback()
            continue

    # If we exhausted retries, something unexpected happened; re-raise the last error
    raise RuntimeError("Failed to drain node after retries")
