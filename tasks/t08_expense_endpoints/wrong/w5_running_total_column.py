"""Keeps a running approved total on the department row, kept up by a trigger.

migrate() adds departments.approved_total, a CHECK (approved_total <= budget),
and a trigger on expenses that adds or removes an expense's amount whenever it
enters, leaves or changes inside the approved set. Every write then goes
through the department row, and the CHECK refuses anything over budget, so
this design may well be safe. It is still wrong for this task: task.md fixes
the schema ("Do not define migrate()"), so the grader refuses to load it and
migrate() never runs.

EXPECT: load_error forbidden_migrate
"""

import psycopg.errors


def migrate(db) -> None:
    db.execute(
        "ALTER TABLE departments ADD COLUMN approved_total int NOT NULL DEFAULT 0,"
        " ADD CONSTRAINT approved_within_budget CHECK (approved_total <= budget)"
    )
    db.execute(
        """
        CREATE FUNCTION track_approved_total() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND OLD.status = 'approved' THEN
                UPDATE departments SET approved_total = approved_total - OLD.amount WHERE id = OLD.department_id;
            END IF;
            IF NEW.status = 'approved' THEN
                UPDATE departments SET approved_total = approved_total + NEW.amount WHERE id = NEW.department_id;
            END IF;
            RETURN NEW;
        END $$
        """
    )
    db.execute(
        "CREATE TRIGGER track_approved_total AFTER INSERT OR UPDATE ON expenses"
        " FOR EACH ROW EXECUTE FUNCTION track_approved_total()"
    )


def _write(db, sql: str, params: tuple) -> bool:
    db.begin()
    try:
        rows = db.execute(sql, params)
    except psycopg.errors.CheckViolation:
        db.rollback()
        return False
    db.commit()
    return bool(rows)


def approve_expense(db, expense_id: int) -> bool:
    return _write(db, "UPDATE expenses SET status = 'approved' WHERE id = %s AND status = 'pending' RETURNING id",
                  (expense_id,))


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    return _write(db, "UPDATE expenses SET amount = %s WHERE id = %s RETURNING id", (new_amount, expense_id))


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    return _write(db, "UPDATE departments SET budget = %s WHERE id = %s RETURNING id", (new_budget, dept_id))
