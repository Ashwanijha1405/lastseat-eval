import psycopg.errors

def approve_expense(db, expense_id: int) -> bool:
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin()
            # lock the expense row
            expense = db.execute(
                "SELECT id, department_id, amount, status FROM expenses WHERE id = %s FOR UPDATE",
                (expense_id,)
            )[0]
            if expense[3] != 'pending':
                db.rollback()
                return False
            dept_id = expense[1]

            # lock department row
            dept = db.execute(
                "SELECT id, name, budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,)
            )[0]

            # lock all approved expenses for the department
            approved = db.execute(
                "SELECT amount FROM expenses WHERE department_id = %s AND status = 'approved' FOR UPDATE",
                (dept_id,)
            )
            sum_approved = sum(row[0] for row in approved)

            if sum_approved + expense[2] <= dept[2]:
                db.execute(
                    "UPDATE expenses SET status = 'approved' WHERE id = %s",
                    (expense_id,)
                )
                db.commit()
                return True
            else:
                db.rollback()
                return False

        except (
            psycopg.errors.SerializationFailure,
            psycopg.errors.DeadlockDetected,
            psycopg.errors.UniqueViolation,
            psycopg.errors.ExclusionViolation,
            psycopg.errors.LockNotAvailable
        ):
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise
    return False


def edit_expense(db, expense_id: int, new_amount: int) -> bool:
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin()
            # lock the expense row
            expense = db.execute(
                "SELECT id, department_id, amount, status FROM expenses WHERE id = %s FOR UPDATE",
                (expense_id,)
            )[0]
            dept_id = expense[1]

            # lock department row
            dept = db.execute(
                "SELECT id, name, budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,)
            )[0]

            # lock all approved expenses for the department
            approved = db.execute(
                "SELECT amount FROM expenses WHERE department_id = %s AND status = 'approved' FOR UPDATE",
                (dept_id,)
            )
            sum_approved = sum(row[0] for row in approved)

            if expense[3] == 'approved':
                new_total = sum_approved - expense[2] + new_amount
                if new_total > dept[2]:
                    db.rollback()
                    return False

            db.execute(
                "UPDATE expenses SET amount = %s WHERE id = %s",
                (new_amount, expense_id)
            )
            db.commit()
            return True

        except (
            psycopg.errors.SerializationFailure,
            psycopg.errors.DeadlockDetected,
            psycopg.errors.UniqueViolation,
            psycopg.errors.ExclusionViolation,
            psycopg.errors.LockNotAvailable
        ):
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise
    return False


def change_budget(db, dept_id: int, new_budget: int) -> bool:
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin()

            # lock department row
            dept = db.execute(
                "SELECT id, name, budget FROM departments WHERE id = %s FOR UPDATE",
                (dept_id,)
            )[0]

            # lock all approved expenses for the department
            approved = db.execute(
                "SELECT amount FROM expenses WHERE department_id = %s AND status = 'approved' FOR UPDATE",
                (dept_id,)
            )
            sum_approved = sum(row[0] for row in approved)

            if sum_approved <= new_budget:
                db.execute(
                    "UPDATE departments SET budget = %s WHERE id = %s",
                    (new_budget, dept_id)
                )
                db.commit()
                return True
            else:
                db.rollback()
                return False

        except (
            psycopg.errors.SerializationFailure,
            psycopg.errors.DeadlockDetected,
            psycopg.errors.UniqueViolation,
            psycopg.errors.ExclusionViolation,
            psycopg.errors.LockNotAvailable
        ):
            db.rollback()
            continue
        except Exception:
            db.rollback()
            raise
    return False
