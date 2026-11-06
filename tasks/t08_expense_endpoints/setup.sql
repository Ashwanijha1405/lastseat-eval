CREATE TABLE departments (
    id     int PRIMARY KEY,
    name   text NOT NULL,
    budget int NOT NULL CHECK (budget >= 0)
);

CREATE TABLE expenses (
    id            int PRIMARY KEY,
    department_id int NOT NULL REFERENCES departments (id),
    amount        int NOT NULL CHECK (amount > 0),
    status        text NOT NULL CHECK (status IN ('pending', 'approved', 'rejected'))
);
