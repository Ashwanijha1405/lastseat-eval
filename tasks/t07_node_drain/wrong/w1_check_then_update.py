"""Checks every shard with a plain SELECT, then deactivates the node's replicas.

Both drains check before either deactivates, so each sees the other node's
replica of the shared shard still active. They update different rows, so
neither waits, and the shared shard ends with no active replica.

EXPECT: safety
"""


def drain_node(db, node_id):
    db.begin()
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
