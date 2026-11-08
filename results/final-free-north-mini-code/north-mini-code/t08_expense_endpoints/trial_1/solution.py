from psycopg.errors import SerializationFailure, DeadlockDetected

def approve_expense(db, expense_id):
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin(isolation="serializable")
            # lock the expense row
            expense = db.execute(
                "SELECT department_id, amount, status FROM expenses WHERE id = %(id)s FOR UPDATE",
                {"id": expense_id}
            )
            if not expense:
                db.rollback()
                return False
            expense = expense[0]
            dept_id, amount, status = expense
            # lock the department row
            dept = db.execute(
                "SELECT budget FROM departments WHERE id = %(id)s FOR UPDATE",
                {"id": dept_id}
            )
            if not dept:
                db.rollback()
                return False
            budget = dept[0][0]
            # compute current approved total for the department
            approved_total = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE department_id = %(dept_id)s AND status = 'approved'",
                {"dept_id": dept_id}
            )[0][0]
            # check if the expense is pending
            if status != 'pending':
                db.rollback()
                return False
            # check budget constraint
            if approved_total + amount <= budget:
                # approve the expense
                db.execute(
                    "UPDATE expenses SET status = 'approved' WHERE id = %(id)s",
                    {"id": expense_id}
                )
                db.commit()
                return True
            else:
                db.rollback()
                return False
        except (SerializationFailure, DeadlockDetected):
            # transaction aborted – roll back and retry
            try:
                db.rollback()
            except:
                pass
            continue
        except Exception:
            # unexpected error – clean up and re‑raise
            try:
                db.rollback()
            except:
                pass
            raise
    # exhausted retry attempts
    return False

def edit_expense(db, expense_id, new_amount):
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin(isolation="serializable")
            # lock the expense row
            expense = db.execute(
                "SELECT department_id, amount, status FROM expenses WHERE id = %(id)s FOR UPDATE",
                {"id": expense_id}
            )
            if not expense:
                db.rollback()
                return False
            expense = expense[0]
            dept_id, old_amount, status = expense
            # lock the department row
            dept = db.execute(
                "SELECT budget FROM departments WHERE id = %(id)s FOR UPDATE",
                {"id": dept_id}
            )
            if not dept:
                db.rollback()
                return False
            budget = dept[0][0]
            # compute current approved total for the department
            approved_total = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE department_id = %(dept_id)s AND status = 'approved'",
                {"dept_id": dept_id}
            )[0][0]
            # decide if the edit is allowed
            allowed = False
            if status != 'approved':
                # pending or rejected – any amount allowed
                allowed = True
            else:
                new_total = approved_total - old_amount + new_amount
                if new_total <= budget:
                    allowed = True
            if not allowed:
                db.rollback()
                return False
            # perform the amount update
            db.execute(
                "UPDATE expenses SET amount = %(new_amount)s WHERE id = %(id)s",
                {"new_amount": new_amount, "id": expense_id}
            )
            db.commit()
            return True
        except (SerializationFailure, DeadlockDetected):
            try:
                db.rollback()
            except:
                pass
            continue
        except Exception:
            try:
                db.rollback()
            except:
                pass
            raise
    return False

def change_budget(db, dept_id, new_budget):
    max_attempts = 5
    for _ in range(max_attempts):
        try:
            db.begin(isolation="serializable")
            # lock the department row
            dept = db.execute(
                "SELECT budget FROM departments WHERE id = %(id)s FOR UPDATE",
                {"id": dept_id}
            )
            if not dept:
                db.rollback()
                return False
            current_budget = dept[0][0]
            # compute approved total for the department
            approved_total = db.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE department_id = %(dept_id)s AND status = 'approved'",
                {"dept_id": dept_id}
            )[0][0]
            if approved_total <= new_budget:
                db.execute(
                    "UPDATE departments SET budget = %(new_budget)s WHERE id = %(id)s",
                    {"new_budget": new_budget, "id": dept_id}
                )
                db.commit()
                return True
            else:
                db.rollback()
                return False
        except (SerializationFailure, DeadlockDetected):
            try:
                db.rollback()
            except:
                pass
            continue
        except Exception:
            try:
                db.rollback()
            except:
                pass
            raise
    return False
