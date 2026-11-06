CREATE TABLE shifts (
    id   int PRIMARY KEY,
    name text NOT NULL
);

CREATE TABLE doctors (
    id       int PRIMARY KEY,
    name     text NOT NULL,
    shift_id int NOT NULL REFERENCES shifts (id),
    on_call  boolean NOT NULL
);
