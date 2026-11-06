"""Prove the grader before any model is graded (SPEC §2.2).

    python -m lastseat.validate [--task t01_flash_sale]

For every task: the reference PASSes; each wrong/*.py FAILs in exactly the
components its docstring's `EXPECT:` line names (so a variant that fails for
an unintended reason, such as a typo, does not count); every failing schedule
reproduces; nothing hits a harness error. Writes results/validation.md and the
per-solution verdicts and counterexamples under results/validation/.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import re
import sys
from pathlib import Path

from .grade import SCORE_WEIGHTS, grade_in_subprocess
from .task import TASKS_DIR, Task, all_tasks, load_task

RESULTS = Path(__file__).resolve().parent.parent / "results"
_EXPECT = re.compile(r"^EXPECT:\s*(.+?)\s*$", re.MULTILINE)


LOAD_ERRORS = ("forbidden_migrate",)  # load errors a wrong variant may be written to trigger


def expected_failures(path: Path) -> set[str]:
    """What a wrong variant must fail, from its docstring's EXPECT: line: score
    components (`EXPECT: safety, liveness`), or one load error
    (`EXPECT: load_error forbidden_migrate`, returned as {"load_error:forbidden_migrate"})."""
    doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
    m = _EXPECT.search(doc)
    if not m:
        raise ValueError(f"{path}: docstring must explain the bug and end with 'EXPECT: <components>'")
    load = re.fullmatch(r"load_error\s+(\w+)", m.group(1))
    if load:
        if load.group(1) not in LOAD_ERRORS:
            raise ValueError(f"{path}: EXPECT load_error must be one of {LOAD_ERRORS}, got {load.group(1)!r}")
        return {f"load_error:{load.group(1)}"}
    parts = {p.strip() for p in m.group(1).split(",")}
    if not parts or not parts <= set(SCORE_WEIGHTS):
        raise ValueError(f"{path}: EXPECT must list some of {sorted(SCORE_WEIGHTS)}, got {m.group(1)!r}")
    return parts


def failed_components(verdict: dict) -> set[str]:
    return {k for k in SCORE_WEIGHTS if verdict.get("scores", {}).get(k, 0) == 0}


def policy_problems(task: Task) -> list[str]:
    problems = []
    if len(task.solo_checks) < 2:
        problems.append("needs >= 2 solo checks (success path + clean refusal)")
    if not any(task.expects_success(c) for c in task.solo_checks):
        problems.append("needs a solo check that expects success (else safety is always vacuous)")
    if not any(s.must_all_succeed for s in task.scenarios):
        problems.append("needs a concurrent scenario with must_all_succeed: true")
    if not any(not s.must_all_succeed for s in task.scenarios):
        problems.append("needs a safety-only concurrent scenario")
    if len(task.wrong_paths) < 2:
        problems.append("needs >= 2 wrong variants")
    if not task.allow_migrate and "Do not define migrate()" not in task.prompt:
        problems.append("allow_migrate is false, so task.md must say 'Do not define migrate()'")
    if task.setup_sql.strip() not in task.prompt:
        problems.append("task.md must contain setup.sql verbatim (the model must see the real schema)")
    return problems


def check(task: Task, path: Path, verdict: dict, expected: set[str] | None) -> list[str]:
    """Problems with one solution's verdict. expected=None means reference."""
    problems = []
    wanted_load = next((e.split(":", 1)[1] for e in expected or () if e.startswith("load_error:")), None)
    if wanted_load:
        got = verdict.get("load_error") if verdict.get("status") == "load_error" else None
        return [] if got == wanted_load else [f"expected load_error {wanted_load}, got status "
                                              f"{verdict.get('status')} ({verdict.get('load_error')})"]
    if verdict.get("status") != "graded":
        detail = verdict.get("harness_detail") or f"{verdict.get('load_error')}: {verdict.get('load_detail')}"
        return [f"status {verdict.get('status')} ({detail})"]
    if not verdict.get("reproducible"):
        problems.append("a failing schedule did not reproduce on re-run")
    failed = failed_components(verdict)
    if expected is None and failed:
        problems.append(f"reference must pass, failed {sorted(failed)}")
    if expected is not None and failed != expected:
        problems.append(f"expected to fail {sorted(expected)}, failed {sorted(failed) or 'nothing'}")
    return problems


def _row(task: Task, path: Path, verdict: dict, expected: set[str] | None, problems: list[str]) -> str:
    scores = verdict.get("scores", {})
    marks = " | ".join("✅" if scores.get(k, 0) > 0 else "❌" for k in SCORE_WEIGHTS)
    scenarios = verdict.get("scenarios", [])
    sched = ", ".join(f"{s['schedules']}{'' if s['exhaustive'] else '*'}" for s in scenarios) or "-"
    ces = sorted((RESULTS / "validation" / task.id / path.stem).glob("counterexample_*.txt"))
    links = " ".join(f"[{c.stem.split('_')[-1]}]({c.relative_to(RESULTS).as_posix()})" for c in ces) or "-"
    want = "PASS" if expected is None else "fail " + "+".join(sorted(expected))
    ok = "✅ ok" if not problems else "❌ " + "; ".join(problems)
    return f"| {task.id} | `{path.relative_to(task.directory).as_posix()}` | {want} | {marks} | {sched} | {links} | {ok} |"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validate references and wrong variants.")
    p.add_argument("--task", action="append", help="task id (repeatable); default: all tasks")
    args = p.parse_args(argv)
    tasks = [load_task(TASKS_DIR / t) for t in args.task] if args.task else all_tasks()

    rows, all_problems = [], 0
    for task in tasks:
        for problem in policy_problems(task):
            print(f"[{task.id}] POLICY: {problem}")
            rows.append(f"| {task.id} | - | policy | - | - | - | - | - | ❌ {problem} |")
            all_problems += 1
        for path in [task.reference_path, *task.wrong_paths]:
            try:
                expected = None if path == task.reference_path else expected_failures(path)
            except ValueError as e:
                print(f"[{task.id}] {e}")
                rows.append(f"| {task.id} | `{path.name}` | ? | - | - | - | - | - | ❌ {e} |")
                all_problems += 1
                continue
            out = RESULTS / "validation" / task.id / path.stem
            verdict = grade_in_subprocess(task.directory, path, out)
            problems = check(task, path, verdict, expected)
            all_problems += len(problems)
            status = "ok" if not problems else "PROBLEM: " + "; ".join(problems)
            print(f"[{task.id}] {path.name:32} failed={sorted(failed_components(verdict))} "
                  f"({verdict.get('seconds', '?')}s) -> {status}")
            rows.append(_row(task, path, verdict, expected, problems))

    header = [
        "# Grader validation",
        "",
        f"Generated by `make validate` on {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d} (UTC). "
        "Each reference must pass every component; each wrong variant must fail exactly the "
        "components named in its `EXPECT:` line; every failing schedule must reproduce on re-run.",
        "",
        "Schedules: number explored per concurrent scenario (`*` = cap reached, seeded-random added).",
        "",
        "| task | solution | expected | safety | solo | liveness | schedules | counterexamples | result |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    footer = ["", f"**{'All checks passed.' if not all_problems else f'{all_problems} problem(s).'}**", ""]
    # Only a full run may write the report; a --task run must not drop other tasks' rows.
    report = RESULTS / ("validation.md" if not args.task else "validation_partial.md")
    report.parent.mkdir(exist_ok=True)
    report.write_text("\n".join(header + rows + footer), encoding="utf-8")
    print(f"wrote {report}: {'OK' if not all_problems else f'{all_problems} problem(s)'}")
    return 1 if all_problems else 0


if __name__ == "__main__":
    sys.exit(main())
