# Task: department expense approvals

Each department has a spending budget. Employees submit expenses, which start as pending. Managers approve them in an internal app; near the end of a quarter several managers approve expenses for the same department at about the same moment.

Write the function the app calls when a manager presses "Approve":

```python
def approve_expense(db, expense_id: int) -> bool: ...
```

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

Amounts and budgets are whole currency units. An expense's `department_id` and `amount` never change, and departments' budgets do not change while approvals are happening.

## Behaviour

- If the expense is `pending` and approving it keeps the department's total approved amount within budget (the sum of `amount` over the department's `approved` expenses, including this one, is at most `budget`): set its `status` to `'approved'` and return `True`.
- Otherwise (the expense is not pending, or approving it would exceed the budget): return `False` and change nothing.
- The expense always exists. Only this expense's row may change.

## Rules that must always hold, however many approvals run at the same time

1. For every department, the total amount of its approved expenses never exceeds its budget.
2. Approvals that fit must succeed: if a set of approvals would all succeed when run one after another, each of them must return `True` when they arrive at the same moment.
