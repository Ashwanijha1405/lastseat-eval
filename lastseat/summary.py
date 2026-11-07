"""Summarize a model run: results/<run_id>/summary.md.

    python -m lastseat.summary results/<run_id> [--regrade]

--regrade first grades every saved solution.py again from disk (no API call),
for example after a grader change. The verdict a cell had before its first
re-grade is kept as verdict.prev.json and never overwritten.

Each failed cell gets a failure category (see grade.failure_category):
load, concurrency, spec or harness.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .grade import failure_category, grade_in_subprocess
from .task import TASKS_DIR


def regrade(run: Path) -> None:
    for sol in sorted(run.glob("*/*/trial_*/solution.py")):
        trial = sol.parent
        old_file = trial / "verdict.json"
        old = json.loads(old_file.read_text(encoding="utf-8"))
        prev = trial / "verdict.prev.json"
        if not prev.exists():
            prev.write_text(json.dumps(old, indent=2), encoding="utf-8")
        new = grade_in_subprocess(TASKS_DIR / trial.parent.name, sol, trial)
        new["api"] = old.get("api")
        new["regraded_from_disk"] = True
        old_file.write_text(json.dumps(new, indent=2, default=repr), encoding="utf-8")
        print(f"{trial.relative_to(run).as_posix()}: total {old.get('scores', {}).get('total')}"
              f" -> {new.get('scores', {}).get('total')}  category {failure_category(new)}")
    # A no_code cell has no solution.py: nothing to re-grade.


def _trials(run: Path, model: str, task: str) -> list[tuple[Path, dict | None]]:
    dirs = sorted((run / model / task).glob("trial_*")) or [run / model / task / "trial_1"]
    out = []
    for d in dirs:
        f = d / "verdict.json"
        out.append((d, json.loads(f.read_text(encoding="utf-8")) if f.exists() else None))
    return out


def _cell(d: Path, v: dict | None) -> str:
    if v is None:
        return "missing" + (" (api error)" if (d / "api_error.txt").exists() else "")
    s = v.get("scores", {})
    if v.get("passed"):
        mark = "PASS"
    else:
        cat = failure_category(v)
        detail = v.get("load_error") or v.get("safety_reason")
        mark = f"FAIL [{cat}]" + (f" ({detail})" if detail else "")
    return (f"{mark} {s.get('total', 0):.2f} (sa {s.get('safety', 0):.2f} / so {s.get('solo', 0):.2f}"
            f" / li {s.get('liveness', 0):.2f})")


def summarize(run: Path) -> str:
    meta = json.loads((run / "run_meta.json").read_text(encoding="utf-8"))
    models = [m["slug"] for m in meta["models"]]
    tasks = meta["tasks"]
    cells = {(m, t): _trials(run, m, t) for m in models for t in tasks}
    out = [f"# Run {meta['run_id']} ({meta.get('tier')}, {meta['trials']} trial(s))", ""]
    if meta.get("notes"):
        out += [f"> Note: {meta['notes']}", ""]

    out += ["| task | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for t in tasks:
        row = ["<br>".join(_cell(d, v) for d, v in cells[m, t]) for m in models]
        out.append(f"| {t} | " + " | ".join(row) + " |")
    out.append("")
    for m in models:
        vs = [v for t in tasks for _, v in cells[m, t] if v]
        n = sum(len(cells[m, t]) for t in tasks)
        cats = [failure_category(v) for v in vs if not v.get("passed")]
        counts = ", ".join(f"{c} {cats.count(c)}" for c in dict.fromkeys(cats)) or "none"
        out.append(f"- {m}: {sum(1 for v in vs if v.get('passed'))}/{n} passed, mean score "
                   f"{sum(v.get('scores', {}).get('total', 0) for v in vs) / n:.3f}; failures: {counts}")
    out += ["", "Failure categories: **load** = never graded (syntax, import, missing function, migrate_error,"
            " forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request"
            " that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe"
            " schedule; **harness** = the grader failed.", "", "## Failures", ""]
    for m in models:
        for t in tasks:
            for d, v in cells[m, t]:
                if v is None or v.get("passed"):
                    continue
                api = v.get("api") or {}
                out.append(f"### {m} / {t} / {d.name}: {failure_category(v)}")
                out.append(f"- status `{v.get('status')}`, load_error `{v.get('load_error')}`, "
                           f"safety_reason `{v.get('safety_reason')}`, finish_reason `{api.get('finish_reason')}`, "
                           f"completion_tokens {api.get('completion_tokens')}")
                for key in ("load_detail", "harness_detail"):
                    if v.get(key):
                        out.append(f"- {key}: `{str(v[key])[:300]}`")
                for c in v.get("solo") or []:
                    if not c["passed"]:
                        out.append(f"- solo FAIL: {c['name']}: {c['reason']}")
                for sc in v.get("scenarios") or []:
                    if not (sc.get("safe") and sc.get("live")) or sc.get("status") not in (None, "ok"):
                        out.append(f"- scenario `{sc['name']}`: status {sc.get('status')}, safe={sc.get('safe')} "
                                   f"({sc.get('unsafe_schedules')} unsafe), live={sc.get('live')} "
                                   f"({sc.get('unlive_schedules')} unlive) of {sc.get('schedules')} schedules, "
                                   f"exhaustive={sc.get('exhaustive')}, reproduced={sc.get('all_reproduced')}")
                for f in sorted(d.glob("counterexample_*.txt")):
                    out.append(f"- counterexample: `{f.relative_to(run.parent.parent).as_posix()}`")
                out.append("")
    out += ["## API", "", "| model | task | trial | tokens out | seconds | attempts | finish | provider |",
            "|---|---|---|---|---|---|---|---|"]
    for (m, t), trials in cells.items():
        for d, v in trials:
            api = (v or {}).get("api") or {}
            out.append(f"| {m} | {t} | {d.name} | {api.get('completion_tokens')} | {api.get('seconds')} | "
                       f"{api.get('attempts')} | {api.get('finish_reason')} | {api.get('provider')} |")
    out += ["", f"spent_usd: {meta.get('spent_usd')}, api_calls: {meta.get('api_calls')}, "
            f"sessions: {len(meta.get('sessions', []))}, complete: {meta.get('complete')}"]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Write results/<run_id>/summary.md for a model run.")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--regrade", action="store_true", help="grade every saved solution again first (no API)")
    args = p.parse_args(argv)
    if args.regrade:
        regrade(args.run_dir)
    text = summarize(args.run_dir)
    (args.run_dir / "summary.md").write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
