"""Reference: lock every affected shard row in shard-id order, then check.

Two drains that share a shard both lock that shard's row, so they take
turns; because every drain locks in ascending shard id, no two drains can
hold locks the other is waiting for (no deadlock). The check runs in a new
READ COMMITTED statement after the locks are granted, so it sees every
drain committed by whoever held them before.
"""


def drain_node(db, node_id: str) -> bool:
    db.begin()
    db.execute(
        "SELECT id FROM shards WHERE id IN (SELECT shard_id FROM replicas WHERE node_id = %s)"
        " ORDER BY id FOR UPDATE",
        (node_id,),
    )
    [(orphaned,)] = db.execute(
        "SELECT count(*) FROM replicas r WHERE r.node_id = %(n)s AND r.active"
        " AND NOT EXISTS (SELECT 1 FROM replicas o"
        "   WHERE o.shard_id = r.shard_id AND o.node_id <> %(n)s AND o.active)",
        {"n": node_id},
    )
    if orphaned:
        db.rollback()
        return False
    db.execute("UPDATE replicas SET active = false WHERE node_id = %s", (node_id,))
    db.commit()
    return True
