# Task: room booking rules

Teams book meeting rooms through an internal app. People book rooms, move their bookings to other times (often to another day), and cancel them. All of this happens at the same time, all day. Every room has two rules: its bookings never overlap, and it takes at most 3 bookings per calendar day (UTC), so that there is time to clean it.

Write the three functions the app calls:

```python
def book(db, room_id: int, starts_at: datetime, ends_at: datetime) -> bool: ...
def reschedule(db, booking_id: int, new_starts_at: datetime, new_ends_at: datetime) -> bool: ...
def cancel(db, booking_id: int) -> bool: ...
```

Your module must define all three. Requests to any of them can arrive at the same moment as requests to the others (or to the same function), each on its own database connection. This service handles heavy traffic. Requests that affect different rooms, or different days of the same room, must never wait for each other, even when they arrive at the same moment.

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

Times are timezone-aware `datetime` values. A booking occupies the half-open interval `[starts_at, ends_at)`: two bookings of the same room overlap if each starts before the other ends, so one that ends at 10:00 and one that starts at 10:00 do not overlap. A booking's *day* is the UTC calendar date of its `starts_at`. Every booking, and every time passed to `book` or `reschedule`, starts and ends on the same UTC calendar day, with the start before the end. The room named in a call always exists. A booking never moves to another room.

## Behaviour

**`book(db, room_id, starts_at, ends_at)`**
- If the new booking overlaps no booking of that room, and the room has fewer than 3 bookings on that day: insert it and return `True`.
- Otherwise return `False` and change nothing.

**`reschedule(db, booking_id, new_starts_at, new_ends_at)`**
- If the booking exists, and at its new time it overlaps no *other* booking of its room, and its room would have at most 3 bookings on the new day counting this one: set its `starts_at` and `ends_at` to the new times and return `True`. Its old time does not count against it, so it may move within the same day or overlap its own old slot.
- Otherwise (it does not exist, for example because it was cancelled, or a rule would be broken): return `False` and change nothing.

**`cancel(db, booking_id)`**
- If the booking exists: delete it and return `True`.
- Otherwise return `False`.

## Rules that must always hold, however many requests run at the same time

1. No two bookings of the same room overlap.
2. No room has more than 3 bookings on any UTC calendar day.
3. Requests that fit must succeed: if a set of requests would all return `True` when run one after another, in any order, each of them must return `True` when they arrive at the same moment.
