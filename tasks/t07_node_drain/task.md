# Task: draining a storage node for maintenance

Our database cluster stores data in shards. Every shard has replicas on several storage nodes, and a replica is either active (serving reads and writes) or inactive. Before maintenance, an operator drains a node: all replicas on that node become inactive. Operators often drain different nodes at about the same moment, and one node holds replicas of many shards.

Write the function the operations console calls:

```python
def drain_node(db, node_id: str) -> bool: ...
```

The schema already exists:

```sql
CREATE TABLE nodes (
    id       text PRIMARY KEY,
    hostname text NOT NULL
);

CREATE TABLE shards (
    id int PRIMARY KEY
);

CREATE TABLE replicas (
    shard_id int NOT NULL REFERENCES shards (id),
    node_id  text NOT NULL REFERENCES nodes (id),
    active   boolean NOT NULL,
    PRIMARY KEY (shard_id, node_id)
);
```

Replicas are never added or removed while drains run; only `active` changes.

## Behaviour

- If every shard that has an active replica on this node also has at least one active replica on another node: set `active = false` for all of this node's replicas and return `True`.
- Otherwise (draining would leave some shard with no active replica): return `False` and change nothing. A drain is all or nothing: never deactivate only some of the node's replicas.
- The node always exists. Only this node's replicas may change.

## Rules that must always hold, however many drains run at the same time

1. Every shard always has at least one active replica.
2. Drains that fit must succeed: if a set of drains would all succeed when run one after another, each of them must return `True` when they arrive at the same moment.
