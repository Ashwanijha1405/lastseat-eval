"""Task specs load into typed objects, and malformed specs are rejected."""

import shutil

import pytest

from lastseat.task import TASKS_DIR, TaskSpecError, load_task


def test_t01_loads():
    task = load_task(TASKS_DIR / "t01_flash_sale")

    assert task.entrypoint == "purchase"
    assert len(task.solo_checks) == 3
    assert [s.must_all_succeed for s in task.scenarios] == [False, True]
    # task-wide invariants come first, then the scenario's own
    assert [i.name for i in task.scenarios[1].invariants] == [
        "stock never negative",
        "stock is conserved (started at 6)",
    ]


@pytest.mark.parametrize(
    "original, broken, message",
    [
        # a misspelled optional key would otherwise silently drop a check
        ("expect_sql: SELECT stock = 2 AND NOT", "expect_sqll: SELECT stock = 2 AND NOT", "unknown key"),
        ("must_all_succeed: true", "must_all_succed: true", "missing required key 'must_all_succeed'"),
        ("must_all_succeed: true", "must_all_succeed: yes please", "must be bool"),
        ("entrypoint: purchase\n", "", "missing required key 'entrypoint'"),
        ("id: t01_flash_sale", "id: t99_other", "does not match directory"),
    ],
)
def test_malformed_spec_is_rejected(tmp_path, original, broken, message):
    task_dir = tmp_path / "t01_flash_sale"
    shutil.copytree(TASKS_DIR / "t01_flash_sale", task_dir)
    spec = task_dir / "spec.yaml"
    text = spec.read_text(encoding="utf-8")
    assert original in text
    spec.write_text(text.replace(original, broken, 1), encoding="utf-8")

    with pytest.raises(TaskSpecError, match=message):
        load_task(task_dir)
