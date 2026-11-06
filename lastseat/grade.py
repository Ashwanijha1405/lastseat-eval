"""Grade one solution file against one task (SPEC §6.1).

    python -m lastseat.grade tasks/t01_flash_sale path/to/solution.py --out DIR

Writes DIR/verdict.json and DIR/counterexample_<k>.txt. `grade_in_subprocess`
runs exactly that command, so model code that never returns is killed with its
process instead of leaking a thread into the caller.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .sandbox import LoadError, Solution, load_solution
from .scheduler import (
    Exploration,
    Explorer,
    Invariant,
    ScheduleResult,
    build_template,
    drop_database,
    ensure_role,
)
from .task import ANY_RETURN, Scenario, SoloCheck, Task, load_task

APP_ROLE = "lastseat_app"
MAX_COUNTEREXAMPLES = 3
SCORE_WEIGHTS = {"safety": 0.5, "solo": 0.25, "liveness": 0.25}


@dataclass
class SoloResult:
    name: str
    passed: bool
    reason: str
    trace: str


@dataclass
class ScenarioResult:
    name: str
    must_all_succeed: bool
    status: str  # schedule status that ended exploration early, or "ok"
    schedules: int
    dfs_schedules: int
    exhaustive: bool
    random_seed: int | None
    safe: bool
    live: bool
    unsafe_schedules: int
    unlive_schedules: int
    all_reproduced: bool
    counterexamples: list[str]
    seconds: float


@dataclass
class Verdict:
    task_id: str
    solution: str
    status: str  # "graded" | "load_error" | "harness_error"
    load_error: str | None = None
    load_detail: str | None = None
    harness_detail: str | None = None
    solo: list[SoloResult] = field(default_factory=list)
    scenarios: list[ScenarioResult] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=lambda: {**dict.fromkeys(SCORE_WEIGHTS, 0.0), "total": 0.0})
    passed: bool = False
    reproducible: bool = True
    seconds: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=repr)


def grade(task: Task, source: str, *, solution_label: str = "solution.py", conninfo: str = "",
          max_schedules: int = 2000, random_schedules: int = 200, seed: int = 0) -> Verdict:
    started = time.monotonic()
    verdict = Verdict(task.id, solution_label, "graded")
    try:
        solution = load_solution(source, task.entrypoint)
    except LoadError as e:
        verdict.status, verdict.load_error, verdict.load_detail = "load_error", e.reason, e.detail
        return verdict

    ensure_role(APP_ROLE, conninfo)
    prefix = f"ls_{task.id[:12]}_{os.getpid()}"
    try:
        verdict.solo = [
            _solo(task, solution, check, f"{prefix}_s{n}", conninfo) for n, check in enumerate(task.solo_checks)
        ]
        for n, sc in enumerate(task.scenarios):
            result = _scenario(task, solution, sc, f"{prefix}_c{n}", conninfo,
                               max_schedules=max_schedules, random_schedules=random_schedules, seed=seed)
            verdict.scenarios.append(result)
            if result.status in ("harness_timeout", "nondeterministic"):
                verdict.status = "harness_error"
                verdict.harness_detail = f"scenario {sc.name!r}: {result.status}"
    except _MigrateError as e:
        verdict.status, verdict.load_error, verdict.load_detail = "load_error", "migrate_error", str(e)
        verdict.solo, verdict.scenarios = [], []

    verdict.seconds = round(time.monotonic() - started, 2)
    if verdict.status != "graded":
        return verdict
    components = {
        "safety": all(s.safe for s in verdict.scenarios),
        "solo": all(s.passed for s in verdict.solo),
        "liveness": all(s.live for s in verdict.scenarios),
    }
    verdict.scores = {k: SCORE_WEIGHTS[k] if ok else 0.0 for k, ok in components.items()}
    verdict.scores["total"] = sum(verdict.scores.values())
    verdict.passed = all(components.values())
    verdict.reproducible = all(s.all_reproduced for s in verdict.scenarios)
    return verdict


class _MigrateError(Exception):
    pass


def _build(task: Task, solution: Solution, name: str, seed_sql: str, conninfo: str) -> None:
    try:
        build_template(name, task.setup_sql, seed_sql=seed_sql, migrate=solution.migrate,
                       role=APP_ROLE, conninfo=conninfo)
    except Exception as e:
        drop_database(name, conninfo)
        raise _MigrateError(f"{type(e).__name__}: {e}") from None


def _call(solution: Solution, kwargs: dict[str, Any]):
    return lambda db: solution.entrypoint(db, **kwargs)


def _solo(task: Task, solution: Solution, check: SoloCheck, name: str, conninfo: str) -> SoloResult:
    _build(task, solution, name, check.seed_sql, conninfo)
    invariants = list(task.invariants)
    if check.expect_sql:
        invariants.append(Invariant(f"expected state: {check.expect_sql}", check.expect_sql))
    try:
        with Explorer(name, [_call(solution, check.call)], invariants, role=APP_ROLE, conninfo=conninfo) as ex:
            r = ex.run()
    finally:
        drop_database(name, conninfo)

    reasons = []
    outcome = r.outcomes[0]
    if r.status != "ok":
        reasons.append(r.status)
    elif outcome.kind != "returned":
        reasons.append(outcome.text)
    elif check.expect_return is not ANY_RETURN and not _same_value(outcome.value, check.expect_return):
        reasons.append(f"returned {outcome.value!r}, expected {check.expect_return!r}")
    reasons += [f"violated: {i.name} (got {i.got})" for i in r.invariants if not i.holds]
    header = f"solo check: {check.name}\ncall: {_signature(task, check.call)}\n"
    return SoloResult(check.name, not reasons, "; ".join(reasons), header + r.trace())


def _same_value(got: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or expected is None:
        return got is expected  # 1 is not True; a refusal must be exactly False
    return type(got) is type(expected) and got == expected


def _scenario(task: Task, solution: Solution, sc: Scenario, name: str, conninfo: str, *,
              max_schedules: int, random_schedules: int, seed: int) -> ScenarioResult:
    started = time.monotonic()

    def unlive(r: ScheduleResult) -> bool:
        if any(o.kind == "step_limit" for o in r.outcomes):
            return True
        if not sc.must_all_succeed:
            return False
        succeeded = all(
            o.kind == "returned" and (task.success_means == "returns" or o.value is True) for o in r.outcomes
        )
        return not succeeded or not r.success_holds

    _build(task, solution, name, sc.seed_sql, conninfo)
    requests = [_call(solution, kwargs) for kwargs in sc.requests]
    try:
        with Explorer(name, requests, sc.invariants, role=APP_ROLE, conninfo=conninfo) as ex:
            exp = ex.explore(max_schedules=max_schedules, random_schedules=random_schedules, seed=seed,
                             is_failure=lambda r: not r.invariants_hold or unlive(r))
    finally:
        drop_database(name, conninfo)

    header = f"scenario: {sc.name}\n" + "".join(
        f"R{i + 1}: {_signature(task, kw)}\n" for i, kw in enumerate(sc.requests)
    )
    stopped = exp.harness_error
    if stopped is not None:
        # Exploration stopped early (model_hang, or a harness error the caller
        # reports): nothing about this scenario can be called safe or live.
        return ScenarioResult(sc.name, sc.must_all_succeed, stopped.status, len(exp.results), exp.dfs_schedules,
                              False, exp.random_seed, safe=False, live=False,
                              unsafe_schedules=0, unlive_schedules=0, all_reproduced=True,
                              counterexamples=[header + stopped.trace()],
                              seconds=round(time.monotonic() - started, 2))

    unsafe = [r for r in exp.results if not r.invariants_hold]
    unlive_runs = [r for r in exp.results if unlive(r)]
    return ScenarioResult(
        name=sc.name,
        must_all_succeed=sc.must_all_succeed,
        status="ok",
        schedules=len(exp.results),
        dfs_schedules=exp.dfs_schedules,
        exhaustive=exp.exhaustive,
        random_seed=exp.random_seed,
        safe=not unsafe,
        live=not unlive_runs,
        unsafe_schedules=len(unsafe),
        unlive_schedules=len(unlive_runs),
        all_reproduced=exp.all_reproduced,
        counterexamples=[header + r.trace() + f"reproduced on re-run: {r.reproduced}\n"
                         for r in _distinct(exp)],
        seconds=round(time.monotonic() - started, 2),
    )


def _distinct(exp: Exploration) -> list[ScheduleResult]:
    """First failing schedule of each failure pattern (which invariants broke,
    how each request ended), at most MAX_COUNTEREXAMPLES."""
    seen, picked = set(), []
    for r in exp.failures:
        pattern = (tuple(i.name for i in r.invariants if not i.holds), tuple(o.fingerprint for o in r.outcomes))
        if pattern not in seen:
            seen.add(pattern)
            picked.append(r)
    return picked[:MAX_COUNTEREXAMPLES]


def _signature(task: Task, kwargs: dict[str, Any]) -> str:
    args = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
    return f"{task.entrypoint}(db, {args})"


def write_outputs(verdict: Verdict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdict.json").write_text(verdict.to_json(), encoding="utf-8")
    for old in out.glob("counterexample_*.txt"):
        old.unlink()
    traces = [t for s in verdict.scenarios for t in s.counterexamples]
    traces += [s.trace for s in verdict.solo if not s.passed]
    for k, trace in enumerate(traces[:MAX_COUNTEREXAMPLES], start=1):
        (out / f"counterexample_{k}.txt").write_text(trace, encoding="utf-8")


def grade_in_subprocess(task_dir: Path, solution: Path, out: Path, *, timeout_s: float = 1800) -> dict[str, Any]:
    """Grade in a fresh Python process; returns the parsed verdict.json."""
    cmd = [sys.executable, "-m", "lastseat.grade", str(task_dir), str(solution), "--out", str(out)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"task_id": Path(task_dir).name, "solution": str(solution), "status": "harness_error",
                "harness_detail": f"grading took longer than {timeout_s}s", "passed": False}
    if proc.returncode != 0:
        return {"task_id": Path(task_dir).name, "solution": str(solution), "status": "harness_error",
                "harness_detail": proc.stderr.strip()[-2000:], "passed": False}
    return json.loads((out / "verdict.json").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("task_dir", type=Path)
    p.add_argument("solution", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)

    task = load_task(args.task_dir)
    verdict = grade(task, args.solution.read_text(encoding="utf-8"), solution_label=str(args.solution))
    write_outputs(verdict, args.out)
    print(f"{task.id} {args.solution}: status={verdict.status} passed={verdict.passed} "
          f"scores={verdict.scores} ({verdict.seconds}s)")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)  # don't wait on a request thread that is still spinning in model code
