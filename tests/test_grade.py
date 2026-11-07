"""Grader scoring rules that are not exercised by the task validation suite."""

import json

from lastseat.grade import VACUOUS_SAFETY, grade
from lastseat.task import TASKS_DIR, load_task

T01 = load_task(TASKS_DIR / "t01_flash_sale")

# Every call raises: nothing ever changes, so no schedule can break an invariant.
ALWAYS_RAISES = '''
def purchase(db, product_id, qty):
    db.begin("read committed")
    db.execute("SELECT no_such_column FROM products")
'''

# Always refuses: passes the "refused cleanly" solo check but never sells anything.
ALWAYS_REFUSES = '''
def purchase(db, product_id, qty):
    return False
'''


def test_code_that_never_succeeds_gets_no_safety_credit():
    v = grade(T01, ALWAYS_RAISES)
    assert all(s.safe for s in v.scenarios), "the scheduler itself still sees no unsafe schedule"
    assert v.scores == {"safety": 0.0, "solo": 0.0, "liveness": 0.0, "total": 0.0}
    assert v.safety_reason == VACUOUS_SAFETY


def test_passing_only_refusal_checks_is_still_vacuous():
    v = grade(T01, ALWAYS_REFUSES)
    assert any(s.passed for s in v.solo), "it does pass the refusal check"
    assert v.scores["safety"] == 0.0 and v.safety_reason == VACUOUS_SAFETY


def test_reference_keeps_its_safety_credit():
    v = grade(T01, T01.reference_path.read_text(encoding="utf-8"))
    assert v.scores["safety"] == 0.5 and v.safety_reason is None and v.passed


# --- several entrypoints: each request names the function it calls ------------

TWO_FN_SPEC = """\
id: t99_two_fns
title: Account with deposit and withdraw
entrypoints: [deposit, withdraw]
signature: "deposit(db, k: int) -> bool; withdraw(db, k: int) -> bool"
seed_state_sql: INSERT INTO account VALUES (1, 3);
invariants:
  - name: balance never negative
    sql: SELECT bool_and(n >= 0) FROM account
solo_checks:
  - name: deposit adds
    call: {fn: deposit, args: {k: 5}}
    expect_return: true
    expect_sql: SELECT n = 8 FROM account
  - name: withdraw over balance is refused
    call: {fn: withdraw, args: {k: 4}}
    expect_return: false
    expect_sql: SELECT n = 3 FROM account
concurrent_scenarios:
  - name: deposit and withdraw at once
    requests:
      - {fn: deposit, args: {k: 5}}
      - {fn: withdraw, args: {k: 2}}
    must_all_succeed: false
    invariants:
      - name: no update lost
        sql: SELECT n = 3 + 5 - (CASE WHEN %(r2)s THEN 2 ELSE 0 END) FROM account
"""

SETUP = "CREATE TABLE account (id int PRIMARY KEY, n int NOT NULL);\n"

DEPOSIT = '''
def deposit(db, k):
    db.begin("read committed")
    db.execute("UPDATE account SET n = n + %s WHERE id = 1", (k,))
    db.commit()
    return True
'''
SAFE_WITHDRAW = '''
def withdraw(db, k):
    db.begin("read committed")
    rows = db.execute("UPDATE account SET n = n - %s WHERE id = 1 AND n >= %s RETURNING n", (k, k))
    db.commit()
    return bool(rows)
'''
# Reads, then writes an absolute value: a deposit committed in between is lost.
RACY_WITHDRAW = '''
def withdraw(db, k):
    db.begin("read committed")
    n = db.execute("SELECT n FROM account WHERE id = 1")[0][0]
    if n < k:
        db.commit()
        return False
    db.execute("UPDATE account SET n = %s WHERE id = 1", (n - k,))
    db.commit()
    return True
'''


def _two_fn_task(tmp_path):
    d = tmp_path / "t99_two_fns"
    d.mkdir()
    (d / "spec.yaml").write_text(TWO_FN_SPEC, encoding="utf-8")
    (d / "setup.sql").write_text(SETUP, encoding="utf-8")
    (d / "task.md").write_text("Write deposit and withdraw.\n\n" + SETUP, encoding="utf-8")
    return load_task(d)


def test_requests_can_call_different_functions(tmp_path):
    task = _two_fn_task(tmp_path)
    v = grade(task, DEPOSIT + SAFE_WITHDRAW)
    assert v.passed, v
    assert [str(c.call) for c in task.solo_checks] == ["deposit(db, k=5)", "withdraw(db, k=4)"]
    # More than one schedule: the scheduler really interleaves the two functions.
    assert v.scenarios[0].schedules > 1


def test_a_race_between_two_different_functions_is_caught(tmp_path):
    task = _two_fn_task(tmp_path)
    v = grade(task, DEPOSIT + RACY_WITHDRAW)
    assert [s.passed for s in v.solo] == [True, True], "each function is fine on its own"
    assert v.scores["safety"] == 0.0 and v.safety_reason is None
    trace = v.scenarios[0].counterexamples[0]
    assert "R1: deposit(db, k=5)\nR2: withdraw(db, k=2)\n" in trace and "no update lost" in trace


def test_a_missing_second_function_is_a_load_error(tmp_path):
    v = grade(_two_fn_task(tmp_path), DEPOSIT)
    assert v.status == "load_error" and v.load_error == "missing_entrypoint" and "'withdraw'" in v.load_detail


# --- allow_migrate: false (t08: the schema is fixed) ---------------------------

T08 = load_task(TASKS_DIR / "t08_expense_endpoints")


def test_a_task_can_forbid_migrate_and_it_never_runs():
    # If this migrate() ran, the verdict would be migrate_error instead.
    source = T08.reference_path.read_text(encoding="utf-8") + (
        "\n\ndef migrate(db):\n    raise RuntimeError('migrate() ran')\n"
    )
    v = grade(T08, source)
    assert T08.allow_migrate is False
    assert v.status == "load_error" and v.load_error == "forbidden_migrate"
    assert v.solo == [] and v.scenarios == [] and v.scores["total"] == 0.0


# --- failure category per failed cell -------------------------------------------

from lastseat.grade import failure_category  # noqa: E402

SAFE = {"safe": True, "live": True}


def graded(solo_ok=True, safe=True, live=True):
    return {"status": "graded", "passed": False, "solo": [{"passed": solo_ok}],
            "scenarios": [{"safe": safe, "live": live}, SAFE]}


def test_failure_categories():
    assert failure_category({"status": "graded", "passed": True}) is None
    assert failure_category({"status": "load_error", "load_error": "forbidden_migrate"}) == "load"
    assert failure_category({"status": "load_error", "load_error": "no_code"}) == "load"
    assert failure_category({"status": "harness_error"}) == "harness"
    assert failure_category(graded(safe=False)) == "concurrency"
    assert failure_category(graded(solo_ok=False, safe=False)) == "concurrency", "a real counterexample wins"
    assert failure_category(graded(solo_ok=False)) == "spec"
    assert failure_category(graded(solo_ok=False, live=False)) == "spec", "e.g. every call raises"
    assert failure_category(graded(live=False)) == "concurrency"


def test_verdict_json_carries_the_category():
    import json
    v = grade(T01, ALWAYS_RAISES)
    assert json.loads(v.to_json())["failure_category"] == "spec"


# --- must_not_block: independent requests must never wait for each other ------

def _t10_independent_only():
    """t10 with only its must_not_block scenarios (and one solo check), to keep the test fast."""
    import dataclasses
    t10 = load_task(TASKS_DIR / "t10_room_rules_scaled")
    return dataclasses.replace(t10, scenarios=tuple(s for s in t10.scenarios if s.must_not_block),
                               solo_checks=t10.solo_checks[:1])


def test_a_whole_room_lock_fails_must_not_block():
    from lastseat.grade import BLOCKED, failure_category
    task = _t10_independent_only()
    v = grade(task, (task.directory / "wrong" / "w5_whole_room_lock.py").read_text(encoding="utf-8"))
    by_name = {s.name: s for s in v.scenarios}
    assert all(s.safe for s in v.scenarios) and v.scores["safety"] == 0.5
    assert v.scores["liveness"] == 0.0 and v.liveness_reason == BLOCKED
    assert failure_category(json.loads(v.to_json())) == "concurrency"
    different_rooms = by_name["bookings of different rooms on the same day never wait"]
    assert different_rooms.live and different_rooms.blocked_schedules == 0   # different rows: no wait
    same_room = [s for s in v.scenarios if s is not different_rooms]
    assert all(not s.live and s.blocked_schedules > 0 and s.unlive_schedules == 0 for s in same_room)
    assert all(s.all_reproduced for s in same_room)
    ce = same_room[0].counterexamples[0]
    assert "blocked (waiting for R" in ce and f"BLOCKED ({BLOCKED})" in ce


def test_the_per_day_advisory_lock_passes_must_not_block():
    task = _t10_independent_only()
    v = grade(task, task.reference_path.read_text(encoding="utf-8"))
    assert v.passed and v.liveness_reason is None
    assert all(s.must_not_block and s.blocked_schedules == 0 for s in v.scenarios)


def test_waiting_is_fine_where_must_not_block_is_not_set():
    """The same whole-room lock on t09 (no must_not_block): requests wait, and that is allowed."""
    t09 = load_task(TASKS_DIR / "t09_room_rules")
    v = grade(t09, (TASKS_DIR / "t10_room_rules_scaled" / "wrong" / "w5_whole_room_lock.py").read_text(encoding="utf-8"))
    assert v.passed and all(s.blocked_schedules == 0 for s in v.scenarios)
