# Task: payment creation with idempotency keys

Our checkout page creates a payment when the customer presses "Pay". Mobile networks are unreliable: the app retries a request when it does not get a response in time, and customers double-click. To make retries safe, the app generates one idempotency key per checkout and sends the same key with every attempt. Two attempts with the same key can reach our servers at the same moment.

Write the function that creates the payment:

```python
def create_payment(db, idempotency_key: str, customer_id: int, amount: int) -> int: ...
```

The schema already exists:

```sql
CREATE TABLE payments (
    id              int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idempotency_key text NOT NULL,
    customer_id     int NOT NULL,
    amount          int NOT NULL CHECK (amount > 0)
);
```

## Behaviour

- If no payment with this `idempotency_key` exists yet: insert one row into `payments` with this `idempotency_key`, `customer_id` and `amount`, and return its `id`.
- If a payment with this `idempotency_key` already exists: insert nothing and return the `id` of the existing payment.
- Every attempt with the same key carries the same `customer_id` and `amount`. `amount` is a positive integer.
- The function must return the payment's `id` as an `int` (never `None`) and must not raise.

## Rules that must always hold, however many attempts run at the same time

1. There is never more than one payment with the same `idempotency_key`.
2. Every attempt succeeds: when several attempts with the same key arrive at the same moment, each of them returns the `id` of the one payment stored for that key. Attempts with different keys each create and return their own payment.
