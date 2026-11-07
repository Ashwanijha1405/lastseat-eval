"""Docker side of the official-CLI provider (claude -p, agy --print): prepare a run, grade its answers.

    python -m lastseat.official_cli prepare (--run-id <id> | --new) --model claude-opus-5-5 \
        --trials 3 --task t01_flash_sale ...
    python lastseat/cli_host.py results/<id>          # on the host: asks the CLI
    python -m lastseat.official_cli grade results/<id>

The prompt is exactly what the OpenRouter runner sends (contract + task.md).
These cells carry source "official-cli" and summary.md shows them in their
own table: the CLI adds its own system prompt (see cli_host.py).
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from .runner import (RESULTS, SCHEDULER_CAPS, _write_json, build_prompt, extract_code, git_commit,
                     postgres_version)
from .grade import grade_in_subprocess
from .task import TASKS_DIR, all_tasks, load_task

SOURCE = "official-cli"


def prepare(args: argparse.Namespace) -> int:
    tasks = [load_task(TASKS_DIR / t) for t in args.task] if args.task else all_tasks()
    if not args.run_id and not args.new:
        print("pass --run-id <id> to continue a run, or --new to start one (never implicit)")
        return 2
    run_id = args.run_id or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-cli"
    run_dir = RESULTS / run_id
    meta_file = run_dir / "run_meta.json"
    slug = args.slug or args.model
    config = SOURCE if args.cli == "claude" else f"{SOURCE}:{args.cli}"
    signature = {"config": config, "models": [args.model], "tasks": [t.id for t in tasks],
                 "trials": args.trials, "dry_run": False}
    if meta_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta.get("signature") != signature:
            print(f"refusing: {run_id} was prepared for {meta.get('signature')}, not {signature}")
            return 2
    else:
        meta = {"run_id": run_id, "source": SOURCE, "signature": signature,
                "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "git_commit": git_commit(), "dry_run": False, "trials": args.trials, "config": config,
                "tier": "subscription", "tasks": [t.id for t in tasks],
                "models": [{"slug": slug, "id": args.model, "source": SOURCE}],
                "cli": {"name": args.cli,
                        "effort": args.effort if args.cli == "claude" else "set by the model id"},
                "postgres_version": postgres_version(),
                "scheduler_caps": SCHEDULER_CAPS, "spent_usd": 0.0, "complete": False, "sessions": []}
    for t in tasks:
        for n in range(1, args.trials + 1):
            d = run_dir / slug / t.id / f"trial_{n}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "prompt.txt").write_text(build_prompt(t), encoding="utf-8", newline="\n")
    run_dir.mkdir(parents=True, exist_ok=True)
    for src in args.reuse_from or []:
        problem = reuse(run_dir, meta, RESULTS / src)
        if problem:
            print(f"refusing to reuse {src}: {problem}")
            return 2
    _write_json(meta_file, meta)
    print(f"prepared {run_dir} ({len(tasks)} task(s) x {args.trials} trial(s), model {args.model})")
    print(f"RUN_ID={run_id}")
    return 0


NOT_COPIED = ("verdict.json", "verdict.prev.json", "solution.py", "prompt.txt")


def _text(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")  # a git checkout may add CRs


def reuse(run_dir: Path, meta: dict, src: Path) -> str | None:
    """Copy answered trials of an earlier run with the same model, CLI and effort
    into the empty trial slots of the same number, when the prompt is identical.
    The copy is graded again by the current grader (verdicts are not copied).
    Returns why the source run cannot be used, or None."""
    src_meta = json.loads((src / "run_meta.json").read_text(encoding="utf-8"))
    mine, theirs = meta["models"][0], src_meta["models"][0]
    for what, a, b in (("source", SOURCE, src_meta.get("source")), ("model", mine["id"], theirs["id"]),
                       ("cli", meta["cli"]["name"], src_meta["cli"].get("name", "claude")),  # runs before agy: claude
                       ("effort", meta["cli"]["effort"], src_meta["cli"]["effort"])):
        if a != b:
            return f"{what} differs ({b!r}, this run has {a!r})"
    for d in sorted(run_dir.glob(f"{mine['slug']}/*/trial_*")):
        s = src / theirs["slug"] / d.parent.name / d.name
        cell = f"{d.parent.name}/{d.name}"
        if (d / "cli_response.json").exists() or not (s / "cli_response.json").exists():
            continue
        if _text(s / "prompt.txt") != _text(d / "prompt.txt"):
            print(f"  not reusing {src.name}/{cell}: the prompt changed since")
            continue
        for f in s.iterdir():
            if f.is_file() and f.name not in NOT_COPIED and not f.name.startswith("counterexample_"):
                (d / f.name).write_bytes(f.read_bytes())
        meta.setdefault("reused", {})[cell] = f"{src.name}/{theirs['slug']}/{cell}"
        print(f"  reused {src.name}/{cell} (CLI {src_meta['cli'].get('version')})")
    return None


def grade(run_dir: Path) -> int:
    meta_file = run_dir / "run_meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    [model] = meta["models"]
    missing = 0
    for t in meta["tasks"]:
        for n in range(1, meta["trials"] + 1):
            d = run_dir / model["slug"] / t / f"trial_{n}"
            if (d / "verdict.json").exists():
                continue
            if not (d / "cli_response.json").exists():
                missing += 1
                continue
            api = json.loads((d / "api.json").read_text(encoding="utf-8"))
            code = extract_code((d / "raw_response.txt").read_text(encoding="utf-8"))
            if code is None:
                verdict = {"task_id": t, "status": "load_error", "load_error": "no_code", "failure_category": "load",
                           "passed": False, "scores": {"safety": 0.0, "solo": 0.0, "liveness": 0.0, "total": 0.0}}
            else:
                (d / "solution.py").write_text(code, encoding="utf-8")
                verdict = grade_in_subprocess(TASKS_DIR / t, d / "solution.py", d)
            verdict["api"] = api
            _write_json(d / "verdict.json", verdict)
            print(f"  graded {d.relative_to(run_dir).as_posix()}: status={verdict.get('status')} "
                  f"passed={verdict.get('passed')} total={verdict.get('scores', {}).get('total')}", flush=True)
    meta["complete"] = missing == 0
    meta["api_calls"] = sum(s.get("calls", 0) for s in meta.get("sessions", []))
    _write_json(meta_file, meta)
    print(f"{run_dir.name}: {missing} cell(s) not answered yet" if missing else f"{run_dir.name}: complete")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="official-cli provider (claude -p): prepare and grade")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("prepare", help="write run_meta.json and every trial's prompt.txt")
    pr.add_argument("--run-id")
    pr.add_argument("--new", action="store_true")
    pr.add_argument("--cli", default="claude", choices=["claude", "antigravity"],
                    help="claude (claude -p) or antigravity (agy --print, for Gemini)")
    pr.add_argument("--model", required=True, help="full model name passed to the CLI's --model")
    pr.add_argument("--slug", help="results folder name (default: the model name)")
    pr.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    pr.add_argument("--trials", type=int, default=3)
    pr.add_argument("--task", action="append")
    pr.add_argument("--reuse-from", action="append", metavar="RUN_ID",
                    help="copy answered trials (same model, CLI, effort, identical prompt) from this run")
    g = sub.add_parser("grade", help="grade every answered, ungraded trial")
    g.add_argument("run_dir", type=Path)
    args = p.parse_args(argv)
    return prepare(args) if args.cmd == "prepare" else grade(args.run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
