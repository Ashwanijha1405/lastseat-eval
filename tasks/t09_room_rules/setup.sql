CREATE TABLE rooms (
    id   int PRIMARY KEY,
    name text NOT NULL
);

CREATE TABLE bookings (
    id        int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_id   int NOT NULL REFERENCES rooms (id),
    starts_at timestamptz NOT NULL,
    ends_at   timestamptz NOT NULL,
    CHECK (starts_at < ends_at)
);
