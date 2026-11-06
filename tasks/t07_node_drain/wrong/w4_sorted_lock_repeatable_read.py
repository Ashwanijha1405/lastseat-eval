"""The reference's sorted shard locks, but under REPEATABLE READ.

The snapshot is taken by the first statement, the shard lock, which may wait
for the other drain to commit. The other drain only locked the shard rows,
so no serialization error is raised, and the check afterwards uses the old
snapshot in which the other node's replicas are still active.

EXPECT: safety
"""


def drain_node(db, node_id):
    db.begin("repeatable read")
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
