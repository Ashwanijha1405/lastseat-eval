"""Deactivates its own replicas first, then locks and checks the other replicas.

Optimistic: write first, verify with FOR UPDATE, roll back if a shard was
orphaned. The verification locks the other nodes' active replicas of the
same shards. Drain A holds A's rows and waits for B's; drain B holds B's rows
and waits for A's: a deadlock, and one valid drain fails with
DeadlockDetected (40P01).

EXPECT: liveness
"""


def drain_node(db, node_id):
    db.begin()
    shards = [r[0] for r in db.execute(
        "UPDATE replicas SET active = false WHERE node_id = %s AND active RETURNING shard_id", (node_id,)
    )]
    if not shards:
        db.commit()
        return True
    rows = db.execute(
        "SELECT shard_id FROM replicas WHERE shard_id = ANY(%s) AND node_id <> %s AND active FOR UPDATE",
        (shards, node_id),
    )
    covered = {r[0] for r in rows}
    if not set(shards) <= covered:
        db.rollback()
        return False
    db.commit()
    return True
