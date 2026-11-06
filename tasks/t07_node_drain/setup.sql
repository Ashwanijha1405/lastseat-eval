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
