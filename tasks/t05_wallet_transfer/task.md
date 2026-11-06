# Task: wallet transfers

Our payments app gives every user a wallet. Users send money to each other, and friends often settle up at the same moment, so a transfer from Alice to Bob and one from Bob to Alice can arrive together, as can several transfers out of the same wallet.

Write the function the app calls for a transfer:

```python
def transfer(db, from_id: int, to_id: int, amount: int) -> bool: ...
```

The schema already exists:

```sql
CREATE TABLE accounts (
    id      int PRIMARY KEY,
    owner   text NOT NULL,
    balance int NOT NULL
);
```

Balances and amounts are whole currency units.

## Behaviour

- If the sender's current balance is at least `amount`: subtract `amount` from the sender's balance, add it to the receiver's balance, and return `True`.
- Otherwise: return `False` and change nothing.
- Both accounts always exist, `from_id != to_id`, and `amount` is a positive integer. Only these two accounts may change.

## Rules that must always hold, however many transfers run at the same time

1. No account's balance ever goes below zero.
2. Money is never created or lost: the total of all balances never changes.
3. Transfers that fit must succeed: if a set of transfers would all succeed when run one after another, each of them must return `True` when they arrive at the same moment, including transfers in opposite directions between the same two accounts.
