CREATE TABLE payments (
    id              int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idempotency_key text NOT NULL,
    customer_id     int NOT NULL,
    amount          int NOT NULL CHECK (amount > 0)
);
