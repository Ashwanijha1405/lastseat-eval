# Task: hospital on-call rota

A hospital divides its doctors into shifts. During a shift, some of its doctors are on call: they must be reachable for emergencies. A doctor can use the staff app to ask to go off call (for example because they feel unwell). Several doctors may press the button at about the same moment.

Write the function the app calls:

```python
def go_off_call(db, doctor_id: int) -> bool: ...
```

The schema already exists:

```sql
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
```

## Behaviour

- If at least one other doctor in the same shift is currently on call: set this doctor's `on_call` to `false` and return `True`.
- Otherwise (this doctor is the only one on call in their shift): return `False` and change nothing.
- The doctor always exists and is on call when the request arrives. Only this doctor's row may change.

## Rules that must always hold, however many requests run at the same time

1. Every shift always has at least one doctor on call.
2. Requests that fit must succeed: if a set of requests would all succeed when run one after another, each of them must return `True` when they arrive at the same moment.
