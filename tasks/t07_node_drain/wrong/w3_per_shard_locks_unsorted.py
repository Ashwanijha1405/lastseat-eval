"""Locks each shard's active replicas one shard at a time, in storage order.

Each shard's check is protected (its active replicas are locked before
counting), but the shards are visited in whatever order the node's replicas
come back. Node A's replicas come back as shard 1 then 2, node B's as shard
2 then 1: drain A holds shard 1's rows and waits for shard 2's while drain B
holds shard 2's and waits for shard 1's. Deadlock (40P01).

EXPECT: liveness
"""


def drain_node(db, node_id):
    db.begin()
    shards = [r[0] for r in db.execute(
        "SELECT shard_id FROM replicas WHERE node_id = %s AND active", (node_id,)
    )]
    for shard in shards:
        active = db.execute(
            "SELECT node_id FROM replicas WHERE shard_id = %s AND active FOR UPDATE", (shard,)
        )
        if not any(n != node_id for (n,) in active):
            db.rollback()
            return False
    db.execute("UPDATE replicas SET active = false WHERE node_id = %s", (node_id,))
    db.commit()
    return True
