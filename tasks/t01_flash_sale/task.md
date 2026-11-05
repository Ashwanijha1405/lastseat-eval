# Task: flash-sale checkout

We run limited-stock flash sales. When a sale opens, many customers press "Buy" within the same second, often for the same product.

Write the checkout function:

```python
def purchase(db, product_id: int, qty: int) -> bool: ...
```

The schema already exists:

```sql
CREATE TABLE products (
    id    int PRIMARY KEY,
    stock int NOT NULL
);

CREATE TABLE orders (
    id         int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id int NOT NULL REFERENCES products (id),
    qty        int NOT NULL CHECK (qty > 0)
);
```

## Behaviour

- If the product currently has at least `qty` units in stock: reduce its `stock` by `qty`, insert exactly one row into `orders` with this `product_id` and `qty`, and return `True`.
- Otherwise: return `False` and change nothing.
- `qty` is always a positive integer, and the product always exists.

## Rules that must always hold, however many purchases run at the same time

1. A product's `stock` never goes below zero.
2. Every unit that leaves stock is recorded by an order: for each product, its current `stock` plus the total `qty` of its orders equals the stock it started with.
3. Purchases that fit must succeed: if a set of purchases would all succeed when run one after another, each of them must return `True` when they arrive at the same moment.
