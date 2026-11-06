# Task: expense app endpoints

Each department has a spending budget. Employees submit expenses, which start as pending. In an internal app, managers approve expenses, employees correct the amount of an expense (also after it was approved), and finance staff adjust department budgets. All of this happens at the same time, all day.

Write the three functions the app calls:

```python
def approve_expense(db, expense_id: int) -> bool: ...
def edit_expense(db, expense_id: int, new_amount: int) -> bool: ...
def change_budget(db, dept_id: int, new_budget: int) -> bool: ...
```

Your module must define all three. Requests to any of them can arrive at the same moment as requests to the others (or to the same function), each on its own database connection.

The schema already exists:

```sql
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
```

Amounts and budgets are whole currency units. A department's *approved total* is the sum of `amount` over its expenses whose `status` is `'approved'`. An expense's `department_id` never changes. The expense or department named in a call always exists, `new_amount` is always greater than 0, and `new_budget` is always at least 0.

## Behaviour

**`approve_expense(db, expense_id)`**
- If the expense is `pending` and approving it keeps its department's approved total (including this expense) at most the department's `budget`: set its `status` to `'approved'` and return `True`.
- Otherwise (not pending, or it would exceed the budget): return `False` and change nothing.

**`edit_expense(db, expense_id, new_amount)`**
- If the expense is `approved`, the change is allowed only if the department's approved total, with this expense at `new_amount`, stays at most the `budget`.
- If the expense is not approved, the change is always allowed.
- If allowed: set its `amount` to `new_amount` and return `True`. Otherwise return `False` and change nothing. The status never changes.

**`change_budget(db, dept_id, new_budget)`**
- If the department's approved total is at most `new_budget`: set its `budget` to `new_budget` and return `True`.
- Otherwise return `False` and change nothing.

Each call may change only the one row it is about (the expense, or the department).

## Rules that must always hold, however many requests run at the same time

1. For every department, the approved total never exceeds its budget.
2. Requests that fit must succeed: if a set of requests would all return `True` when run one after another, in any order, each of them must return `True` when they arrive at the same moment.
