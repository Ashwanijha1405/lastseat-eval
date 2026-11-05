CREATE TABLE products (
    id    int PRIMARY KEY,
    stock int NOT NULL
);

CREATE TABLE orders (
    id         int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id int NOT NULL REFERENCES products (id),
    qty        int NOT NULL CHECK (qty > 0)
);
