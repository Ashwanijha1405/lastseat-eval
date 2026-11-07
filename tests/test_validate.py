"""validate: the `EXPECT: blocking` form (fails liveness only by blocking in must_not_block scenarios)."""

import pytest

from lastseat.task import TASKS_DIR, load_task
from lastseat.validate import BLOCKING, check, expected_failures


def _variant(tmp_path, expect):
    p = tmp_path / "w.py"
    p.write_text(f'"""Bug.\n\nEXPECT: {expect}\n"""\n', encoding="utf-8")
    return p


def test_expect_blocking_parses_and_cannot_be_mixed(tmp_path):
    assert expected_failures(_variant(tmp_path, "blocking")) == {BLOCKING}
    with pytest.raises(ValueError):
        expected_failures(_variant(tmp_path, "blocking, safety"))


def _scenario(name, *, safe=True, live=True, unlive=0, blocked=0, mnb=False):
    return {"name": name, "safe": safe, "live": live, "unlive_schedules": unlive, "blocked_schedules": blocked,
            "must_not_block": mnb}


def _verdict(*scenarios):
    return {"status": "graded", "reproducible": True, "scenarios": list(scenarios),
            "scores": {"safety": 0.5, "solo": 0.25, "liveness": 0.0, "total": 0.75}}


T10 = load_task(TASKS_DIR / "t10_room_rules_scaled")


@pytest.mark.parametrize("scenarios, ok", [
    ([_scenario("a"), _scenario("b", live=False, blocked=3, mnb=True)], True),
    ([_scenario("a", live=False, unlive=2), _scenario("b", live=False, blocked=3, mnb=True)], False),  # also unlive
    ([_scenario("a", safe=False), _scenario("b", live=False, blocked=3, mnb=True)], False),            # unsafe
    ([_scenario("a"), _scenario("b", mnb=True)], False),                                                # never blocked
])
def test_expect_blocking_accepts_only_a_pure_blocking_failure(scenarios, ok):
    v = _verdict(*scenarios)
    if any(not s["safe"] for s in scenarios):
        v["scores"]["safety"] = 0.0
    assert (check(T10, T10.reference_path, v, {BLOCKING}) == []) == ok
