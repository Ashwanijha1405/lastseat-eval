"""The scheduler catches known races, passes known-safe code, and is deterministic."""

import math

import psycopg
import pytest

from lastseat.scheduler import Invariant

BOTH_APPLIED = [Invariant("both increments applied", "SELECT n = 2 FROM counter WHERE id = 1")]

ACCOUNTS_SETUP = "CREATE TABLE accounts (id int PRIMARY KEY, balance int NOT NULL);"
ACCOUNTS_SEED = "INSERT INTO accounts VALUES (1, 100), (2, 100);"
MONEY_CONSERVED = [Invariant("money is conserved", "SELECT sum(balance) = 200 FROM accounts")]


def read_then_write(db):
    """Lost update: the new value is computed in Python from a stale read."""
    db.begin()
    [(n,)] = db.execute("SELECT n FROM counter WHERE id = 1")
    db.execute("UPDATE counter SET n = %s WHERE id = 1", (n + 1,))
    db.commit()


def atomic_increment(db):
    db.begin()
    db.execute("UPDATE counter SET n = n + 1 WHERE id = 1")
    db.commit()


def locked_read_then_write(db):
    db.begin()
    [(n,)] = db.execute("SELECT n FROM counter WHERE id = 1 FOR UPDATE")
    db.execute("UPDATE counter SET n = %s WHERE id = 1", (n + 1,))
    db.commit()


def short_tx(db):
    db.begin()
    db.execute("SELECT 1")
    db.commit()


def transfer(src, dst, *, lock_in_id_order=False, retries=0):
    def fn(db):
        first, second = sorted((src, dst)) if lock_in_id_order else (src, dst)
        for _ in range(retries + 1):
            try:
                db.begin()
                for acct in (first, second):
                    delta = -10 if acct == src else 10
                    db.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (delta, acct))
                db.commit()
                return True
            except psycopg.errors.DeadlockDetected:
                db.rollback()
        raise RuntimeError("gave up after retries")

    return fn


# --- races are caught, safe code passes ------------------------------------


def test_lost_update_is_caught(explorer):
    result = explorer([read_then_write, read_then_write], BOTH_APPLIED).explore()

    assert result.exhaustive
    assert result.failures
    assert result.all_reproduced
    trace = result.failures[0].trace()
    assert trace.count("SELECT n FROM counter WHERE id = 1 -> [(0,)]") == 2
    assert "INVARIANT VIOLATED: both increments applied  (got [(False,)])" in trace


@pytest.mark.parametrize("fn", [atomic_increment, locked_read_then_write])
def test_safe_increment_passes_every_schedule(explorer, fn):
    result = explorer([fn, fn], BOTH_APPLIED).explore()

    assert result.exhaustive
    assert result.failures == []
    assert all(o.kind == "returned" for r in result.results for o in r.outcomes)
    # The second request really waited on the first one's row lock somewhere.
    assert any("blocked (waiting for R" in r.trace() for r in result.results)


def test_autocommit_statement_can_be_interleaved_before_its_commit(explorer):
    """One statement, no explicit transaction, still loses an update.

    The subquery is evaluated once from the statement's snapshot. When the row
    lock is released Postgres re-checks the updated row, not the subquery.
    Found only because the implicit COMMIT is its own step.
    """

    def subquery_increment(db):
        db.execute("UPDATE counter SET n = (SELECT n FROM counter WHERE id = 1) + 1 WHERE id = 1")

    result = explorer([subquery_increment, subquery_increment], BOTH_APPLIED).explore()

    assert result.exhaustive
    assert result.failures
    assert result.all_reproduced


# --- determinism ------------------------------------------------------------


def test_same_schedule_twice_gives_same_trace(explorer):
    ex = explorer([read_then_write, read_then_write], BOTH_APPLIED)
    failing = ex.explore().failures[0]

    for _ in range(3):
        again = ex.run(failing.choices)
        assert again.trace() == failing.trace()
        assert again.fingerprint() == failing.fingerprint()


def test_exploration_is_deterministic(explorer):
    ex = explorer([read_then_write, locked_read_then_write], BOTH_APPLIED)
    a, b = ex.explore(), ex.explore()

    assert [r.trace() for r in a.results] == [r.trace() for r in b.results]


def test_deadlock_is_reported_with_the_same_victim_every_time(explorer):
    ex = explorer(
        [transfer(1, 2), transfer(2, 1)], MONEY_CONSERVED, setup=ACCOUNTS_SETUP, seed=ACCOUNTS_SEED
    )
    result = ex.explore(is_failure=lambda r: any(o.kind != "returned" for o in r.outcomes))

    assert result.exhaustive
    assert result.failures
    assert result.all_reproduced
    deadlock = result.failures[0]
    assert "40P01 DeadlockDetected" in deadlock.trace()
    assert deadlock.invariants_hold  # the victim was rolled back, money intact
    for _ in range(5):
        assert ex.run(deadlock.choices).fingerprint() == deadlock.fingerprint()


# --- exploration covers every interleaving exactly once -----------------------


def test_two_requests_of_three_steps_have_20_interleavings(explorer):
    result = explorer([short_tx, short_tx], []).explore()

    assert result.exhaustive
    assert len(result.results) == math.comb(6, 3)
    assert len({r.choices for r in result.results}) == len(result.results)


def test_three_autocommit_requests_have_90_interleavings(explorer):
    def one_select(db):  # statement + its implicit COMMIT = 2 steps
        db.execute("SELECT 1")

    result = explorer([one_select] * 3, []).explore()

    assert result.exhaustive
    assert len(result.results) == math.factorial(6) // (2 * 2 * 2)


def test_capped_exploration_falls_back_to_seeded_random(explorer):
    ex = explorer([short_tx, short_tx], [])
    a = ex.explore(max_schedules=5, random_schedules=10, seed=7)
    b = ex.explore(max_schedules=5, random_schedules=10, seed=7)

    assert not a.exhaustive
    assert (a.dfs_schedules, a.random_seed, len(a.results)) == (5, 7, 15)
    assert [r.choices for r in a.results] == [r.choices for r in b.results]


# --- liveness: valid concurrent requests can all succeed ----------------------


@pytest.mark.parametrize(
    "options", [{"lock_in_id_order": True}, {"retries": 3}], ids=["lock-order", "retry"]
)
def test_opposite_transfers_both_succeed_when_written_correctly(explorer, options):
    ex = explorer(
        [transfer(1, 2, **options), transfer(2, 1, **options)],
        MONEY_CONSERVED,
        setup=ACCOUNTS_SETUP,
        seed=ACCOUNTS_SEED,
    )
    result = ex.explore()

    assert result.exhaustive
    assert result.failures == []
    assert all(o.value is True for r in result.results for o in r.outcomes)


# --- harness guards -----------------------------------------------------------


def test_endless_retry_loop_hits_step_limit(explorer):
    def spin(db):
        while True:
            try:
                db.execute("SELECT 1")
            except Exception:
                pass

    [schedule] = explorer([spin], [], step_limit=10).explore().results

    assert schedule.outcomes[0].kind == "step_limit"


def test_open_transaction_is_rolled_back_with_warning(explorer):
    def forgets_commit(db):
        db.begin()
        db.execute("UPDATE counter SET n = 1 WHERE id = 1")
        return True

    kept_nothing = [Invariant("update was not kept", "SELECT n = 0 FROM counter WHERE id = 1")]
    [schedule] = explorer([forgets_commit], kept_nothing).explore().results

    assert schedule.invariants_hold
    assert schedule.warnings
    assert "harness rolled it back" in schedule.trace()


def test_one_statement_per_execute(explorer):
    def two_statements(db):
        db.execute("UPDATE counter SET n = 1 WHERE id = 1; UPDATE counter SET n = 2 WHERE id = 1")

    nothing_ran = [Invariant("nothing ran", "SELECT n = 0 FROM counter WHERE id = 1")]
    [schedule] = explorer([two_statements], nothing_ran).explore().results

    assert schedule.outcomes[0].kind == "raised"
    assert "cannot insert multiple commands" in schedule.outcomes[0].text
    assert schedule.invariants_hold


def test_unknown_isolation_level_is_rejected(explorer):
    def bad_isolation(db):
        db.begin("snapshot")

    [schedule] = explorer([bad_isolation], []).explore().results

    assert schedule.outcomes[0].text.startswith("raised ValueError")


def test_statement_that_never_finishes_is_a_harness_timeout(explorer):
    def sleepy(db):
        db.execute("SELECT pg_sleep(30)")

    result = explorer([sleepy], [], schedule_timeout_s=0.5).explore()

    assert result.harness_error is not None
    assert result.harness_error.status == "harness_timeout"
