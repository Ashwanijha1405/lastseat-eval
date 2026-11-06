# Task: meeting-room booking

Our office app lets employees book meeting rooms. Popular rooms are booked the moment the day's calendar opens, so several people often try to book the same room for similar times at about the same moment.

Write the function the app calls when someone presses "Book":

```python
from datetime import datetime

def book_room(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool: ...
```

The schema already exists:

```sql
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
```

A booking occupies its room from `starts_at` up to, but not including, `ends_at`. So a booking from 10:00 to 11:00 and another from 11:00 to 12:00 do not overlap and may both exist; 10:00 to 11:00 and 10:30 to 11:30 do overlap.

## Behaviour

- If the room has no existing booking that overlaps the requested time: insert exactly one row into `bookings` with this `room_id`, `starts_at` and `ends_at`, and return `True`.
- Otherwise: return `False` and change nothing.
- The room always exists. `starts_at` and `ends_at` are timezone-aware `datetime` values with `starts_at < ends_at`.

## Rules that must always hold, however many requests run at the same time

1. No two bookings of the same room overlap.
2. Bookings that fit must succeed: if a set of booking requests would all succeed when run one after another, each of them must return `True` when they arrive at the same moment.
