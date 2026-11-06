"""Task loader: turns tasks/<id>/ into typed objects.

Specs are parsed strictly: an unknown or misspelled key is an error, so a typo
such as `must_all_succed` cannot silently weaken grading.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .scheduler import Invariant

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


class TaskSpecError(Exception):
    pass


class _AnyReturn:
    def __repr__(self) -> str:
        return "<any return value>"


# expect_return omitted: any value counts, as long as the call returns
# (no exception) and expect_sql holds.
ANY_RETURN = _AnyReturn()

# What counts as a successful request in a must_all_succeed scenario.
SUCCESS_MEANS = ("returns_true", "returns")


@dataclass(frozen=True)
class SoloCheck:
    name: str
    seed_sql: str
    call: dict[str, Any]
    expect_return: Any  # or ANY_RETURN
    expect_sql: str | None  # may use %(r1)s for the returned value


@dataclass(frozen=True)
class Scenario:
    name: str
    seed_sql: str
    requests: tuple[dict[str, Any], ...]
    must_all_succeed: bool
    # Safety invariants (task-wide first, then this scenario's) followed by
    # success checks (kind="success"; only in must_all_succeed scenarios).
    invariants: tuple[Invariant, ...]


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    entrypoint: str
    signature: str
    directory: Path
    setup_sql: str
    prompt: str
    success_means: str  # one of SUCCESS_MEANS
    invariants: tuple[Invariant, ...]
    solo_checks: tuple[SoloCheck, ...]
    scenarios: tuple[Scenario, ...]

    @property
    def reference_path(self) -> Path:
        return self.directory / "reference.py"

    @property
    def wrong_paths(self) -> list[Path]:
        return sorted((self.directory / "wrong").glob("*.py"))


def load_task(directory: Path | str) -> Task:
    directory = Path(directory)
    where = directory / "spec.yaml"
    try:
        raw = yaml.safe_load(where.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise TaskSpecError(f"{where}: {e}") from None

    spec = _Fields(raw, str(where))
    task_id = spec.req("id", str)
    if task_id != directory.name:
        raise TaskSpecError(f"{where}: id {task_id!r} does not match directory {directory.name!r}")
    default_seed = spec.opt("seed_state_sql", str, "")
    success_means = spec.opt("success_means", str, "returns_true")
    if success_means not in SUCCESS_MEANS:
        raise TaskSpecError(f"{where}: success_means must be one of {SUCCESS_MEANS}, got {success_means!r}")
    invariants = tuple(_invariant(i, f"{where}: invariants[{n}]") for n, i in enumerate(spec.opt("invariants", list, [])))

    solo = []
    for n, raw_check in enumerate(spec.req("solo_checks", list)):
        ctx = f"{where}: solo_checks[{n}]"
        f = _Fields(raw_check, ctx)
        check = SoloCheck(
            name=f.req("name", str),
            seed_sql=f.opt("seed_sql", str, default_seed),
            call=f.req("call", dict),
            expect_return=f.opt("expect_return", object, ANY_RETURN),
            expect_sql=f.opt("expect_sql", str, None),
        )
        if check.expect_return is ANY_RETURN and not check.expect_sql:
            raise TaskSpecError(f"{ctx}: needs expect_return, expect_sql, or both")
        solo.append(check)
        f.done()

    scenarios = []
    for n, raw_sc in enumerate(spec.req("concurrent_scenarios", list)):
        ctx = f"{where}: concurrent_scenarios[{n}]"
        f = _Fields(raw_sc, ctx)
        requests = f.req("requests", list)
        if len(requests) < 2 or not all(isinstance(r, dict) for r in requests):
            raise TaskSpecError(f"{ctx}: requests must be a list of at least two argument mappings")
        extra = tuple(_invariant(i, f"{ctx}: invariants[{k}]") for k, i in enumerate(f.opt("invariants", list, [])))
        must_all_succeed = f.req("must_all_succeed", bool)
        success = tuple(
            _invariant(i, f"{ctx}: success_sql[{k}]", kind="success")
            for k, i in enumerate(f.opt("success_sql", list, []))
        )
        if success and not must_all_succeed:
            raise TaskSpecError(f"{ctx}: success_sql is only allowed when must_all_succeed is true")
        scenarios.append(
            Scenario(
                name=f.req("name", str),
                seed_sql=f.opt("seed_sql", str, default_seed),
                requests=tuple(requests),
                must_all_succeed=must_all_succeed,
                invariants=invariants + extra + success,
            )
        )
        f.done()

    task = Task(
        id=task_id,
        title=spec.req("title", str),
        entrypoint=spec.req("entrypoint", str),
        signature=spec.req("signature", str),
        directory=directory,
        setup_sql=(directory / "setup.sql").read_text(encoding="utf-8"),
        prompt=(directory / "task.md").read_text(encoding="utf-8"),
        success_means=success_means,
        invariants=invariants,
        solo_checks=tuple(solo),
        scenarios=tuple(scenarios),
    )
    spec.done()
    return task


def all_tasks() -> list[Task]:
    return [load_task(d) for d in sorted(TASKS_DIR.iterdir()) if (d / "spec.yaml").is_file()]


def _invariant(raw: Any, ctx: str, kind: str = "safety") -> Invariant:
    f = _Fields(raw, ctx)
    inv = Invariant(f.req("name", str), f.req("sql", str), kind)
    f.done()
    return inv


class _Fields:
    """Reads keys from one YAML mapping and rejects any key nobody asked for."""

    def __init__(self, raw: Any, ctx: str) -> None:
        if not isinstance(raw, dict):
            raise TaskSpecError(f"{ctx}: expected a mapping")
        self.raw, self.ctx, self.seen = raw, ctx, set()

    def req(self, key: str, kind: type) -> Any:
        if key not in self.raw:
            raise TaskSpecError(f"{self.ctx}: missing required key {key!r}")
        return self.opt(key, kind, None)

    def opt(self, key: str, kind: type, default: Any) -> Any:
        self.seen.add(key)
        if key not in self.raw:
            return default
        value = self.raw[key]
        if not isinstance(value, kind):
            raise TaskSpecError(f"{self.ctx}: {key!r} must be {kind.__name__}, got {type(value).__name__}")
        return value

    def done(self) -> None:
        unknown = sorted(set(self.raw) - self.seen)
        if unknown:
            raise TaskSpecError(f"{self.ctx}: unknown key(s) {unknown}")
