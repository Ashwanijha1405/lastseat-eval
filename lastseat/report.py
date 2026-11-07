"""Build the README's results sections from results/ (never typed by hand).

    python -m lastseat.report            # print the generated sections
    python -m lastseat.report --write    # replace them in README.md, between
                                         # <!-- BEGIN report:NAME --> and <!-- END report:NAME -->

Final runs are the results/final-* directories. Every number comes from their
run_meta.json and per-trial verdict.json / api.json, and from the validation
verdicts under results/validation/. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
README = ROOT / "README.md"
ORDER = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "gemini-3.8-flash-high"]


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def final_runs() -> list[dict]:
    runs = []
    for meta_file in RESULTS.glob("final-*/run_meta.json"):
        meta = _load(meta_file)
        run = meta_file.parent
        model = meta["models"][0]
        trials = {}
        for t in meta["tasks"]:
            for n in range(1, meta["trials"] + 1):
                d = run / model["slug"] / t / f"trial_{n}"
                v = d / "verdict.json"
                trials[t, n] = (d, _load(v) if v.exists() else None)
        runs.append({"dir": run, "meta": meta, "model": model, "trials": trials})
    rank = {m: i for i, m in enumerate(ORDER)}
    return sorted(runs, key=lambda r: (rank.get(r["model"]["id"], len(ORDER)), r["model"]["id"]))


def _route(r: dict) -> tuple[str, str]:
    meta = r["meta"]
    graded = [v for _, v in r["trials"].values() if v]
    if meta.get("source") == "official-cli":
        cli = meta["cli"]
        if cli.get("name", "claude") == "claude":
            version = cli.get("version", "").replace(" (Claude Code)", "")
            return (f"Claude Code `claude -p` {version}, claude.ai Pro login",
                    f"effort `{cli['effort']}`, no tools (`--tools ''`), CLI system prompt included")
        versions = sorted({(v.get("api") or {}).get("cli_version") for v in graded} - {None})
        return (f"Antigravity CLI `agy --print` {', '.join(versions)}, Google sign-in",
                "`-high` variant chosen by model id, every tool action denied, CLI system prompt included")
    providers = sorted({(v.get("api") or {}).get("provider") for v in graded} - {None})
    s = meta.get("settings_sent", {})
    return (f"OpenRouter free tier (served by {', '.join(providers) or '?'})",
            f"reasoning effort `{s.get('reasoning', {}).get('effort')}`, max_tokens {s.get('max_tokens')}, "
            "max_price 0")


def _dates(r: dict) -> str:
    days = {(v.get("api") or {}).get("date_utc", "")[:10] for _, v in r["trials"].values() if v}
    days |= {s["started_utc"][:10] for s in r["meta"].get("sessions", []) if r["meta"].get("source") != "official-cli"}
    days.discard("")
    return ", ".join(sorted(days)) or "-"


def models_section(runs: list[dict]) -> str:
    out = ["| model (exact ID) | route | settings | trials | run dates (UTC) | cells graded | run |",
           "|---|---|---|---|---|---|---|"]
    for r in runs:
        route, settings = _route(r)
        done = sum(1 for _, v in r["trials"].values() if v)
        reused = len(r["meta"].get("reused", {}))
        out.append(f"| `{r['model']['id']}` | {route} | {settings} | {r['meta']['trials']} per task | {_dates(r)} | "
                   f"{done}/{len(r['trials'])}" + (f" ({reused} reused from pilots)" if reused else "")
                   + f" | [`{r['dir'].name}`]({_rel(r['dir'])}/summary.md) |")
    return "\n".join(out)


def results_section(runs: list[dict]) -> str:
    tasks = list(dict.fromkeys(t for r in runs for t, _ in r["trials"]))
    out = ["| task | " + " | ".join(f"`{r['model']['id']}`" for r in runs) + " |",
           "|---|" + "---|" * len(runs)]
    for t in tasks:
        row = []
        for r in runs:
            k = r["meta"]["trials"]
            vs = [r["trials"][t, n][1] for n in range(1, k + 1) if (t, n) in r["trials"]]
            graded = [v for v in vs if v]
            passed = sum(1 for v in graded if v.get("passed"))
            if len(graded) < k:
                row.append(f"{passed}/{len(graded)} (running)" if graded else "running")
            else:
                row.append(f"{passed}/{k} " + ("✅" if passed == k else "❌"))
        out.append(f"| {t} | " + " | ".join(row) + " |")
    ks = sorted({r["meta"]["trials"] for r in runs})
    pk = f"tasks with pass^{ks[0]}" if len(ks) == 1 else "tasks with pass^k"
    totals = {"trials passed": [], "mean score": [], pk: [], "latent_api_error warnings": []}
    for r in runs:
        k = r["meta"]["trials"]
        graded = [v for _, v in r["trials"].values() if v]
        n = len(r["trials"])
        complete = len(graded) == n
        totals["trials passed"].append(f"{sum(1 for v in graded if v.get('passed'))}/{len(graded)}"
                                       + ("" if complete else f" of {n}"))
        totals["mean score"].append(f"{sum(v.get('scores', {}).get('total', 0) for v in graded) / len(graded):.3f}"
                                    if graded else "-")
        per_task = {}
        for (t, _), (_, v) in r["trials"].items():
            per_task.setdefault(t, []).append(v)
        full = [vs for vs in per_task.values() if all(vs)]
        totals[pk].append(f"{sum(1 for vs in full if all(v.get('passed') for v in vs))}/{len(per_task)}")
        totals["latent_api_error warnings"].append(str(sum(len(v.get("warnings") or []) for v in graded)))
    for name, cells in totals.items():
        out.append(f"| **{name}** | " + " | ".join(cells) + " |")
    return "\n".join(out)


def _failed_components(v: dict) -> str:
    if v.get("status") == "load_error":
        return f"load_error `{v.get('load_error')}`"
    if v.get("status") != "graded":
        return "harness_error"
    s = v.get("scores", {})
    return ", ".join(c for c in ("safety", "solo", "liveness") if not s.get(c)) or "none"


def _short(text: str, n: int = 110) -> str:
    line = str(text).strip().splitlines()[0] if str(text).strip() else ""
    return (line[:n] + "…") if len(line) > n else line


def failures_section(runs: list[dict]) -> str:
    out = []
    for r in runs:
        for (t, n), (d, v) in sorted(r["trials"].items()):
            if not v or v.get("passed"):
                continue
            detail = v.get("load_error") or v.get("safety_reason") or v.get("liveness_reason")
            links = [f"[verdict]({_rel(d / 'verdict.json')})"]
            links += [f"[counterexample {i}]({_rel(f)})" for i, f in enumerate(sorted(d.glob("counterexample_*.txt")), 1)]
            out.append(f"- `{r['model']['id']}` · {t} · trial_{n}: **{v.get('failure_category')}**"
                       + (f" ({detail})" if detail else "")
                       + (f": `{_short(v['load_detail'])}`" if v.get("load_detail") else "") + " — " + ", ".join(links))
    warned = [(r, t, n, d, w) for r in runs for (t, n), (d, v) in sorted(r["trials"].items()) if v
              for w in v.get("warnings") or []]
    if warned:
        out += ["", "Warnings (not scored):", ""]
        out += [f"- `{r['model']['id']}` · {t} · trial_{n}: `{w['kind']}` `{w['name']}` "
                f"(line {', '.join(map(str, w['lines']))}) — [solution]({_rel(d / 'solution.py')})"
                for r, t, n, d, w in warned]
    return "\n".join(out) or "No failures."


_ROW = re.compile(r"^\| (t\d\d\w*) \| `([^`]+)` \| ([^|]+) \|.*\| ([^|]+) \|$")


def validation_section() -> str:
    rows = [m.groups() for line in (RESULTS / "validation.md").read_text(encoding="utf-8").splitlines()
            if (m := _ROW.match(line))]
    out = ["| task | solution | expected | observed failures | schedules explored | exhaustive | result |",
           "|---|---|---|---|---|---|---|"]
    ok = 0
    for task, sol, expected, result in rows:
        v = _load(RESULTS / "validation" / task / Path(sol).stem / "verdict.json")
        scs = v.get("scenarios") or []
        observed = "none (PASS)" if v.get("passed") else _failed_components(v)
        if v.get("liveness_reason"):
            observed += f" ({v['liveness_reason']})"
        good = result.strip().endswith("ok")  # validate's own exact check (components named by EXPECT)
        ok += good
        out.append(f"| {task} | `{sol}` | {expected.strip()} | {observed} | {sum(s['schedules'] for s in scs) or '-'} | "
                   f"{'yes' if scs and all(s.get('exhaustive') for s in scs) else ('-' if not scs else 'no (cap + random)')} | "
                   f"{'✅' if good else '❌'} |")
    refs = sum(1 for _, sol, _, _ in rows if sol == "reference.py")
    for v_file in sorted(RESULTS.glob("validation/*/alt_*/verdict.json")):
        v = _load(v_file)
        scs = v.get("scenarios") or []
        waits = sum(s.get("blocked_schedules", 0) for s in scs)
        out.append(f"| {v_file.parent.parent.name} | `alternatives/{v_file.parent.name[4:]}.py` | PASS (alternative; graded separately, not by validate) | "
                   f"{'none (PASS)' if v.get('passed') else _failed_components(v)} | {sum(s['schedules'] for s in scs)} | "
                   f"{'yes' if scs and all(s.get('exhaustive') for s in scs) else 'no (cap + random)'} | "
                   f"{'✅' if v.get('passed') else '❌'} |")
    out.append("")
    out.append(f"{refs} references and {len(rows) - refs} wrong variants; {ok}/{len(rows)} behave as expected. "
               "Full table with per-scenario counts and counterexample links: [results/validation.md](results/validation.md).")
    return "\n".join(out)


def runtime_section(runs: list[dict]) -> str:
    out = ["| model | new calls in the final run (reused pilot trials excluded) | model time per answer (median s) | grading time (total s) | "
           "schedules explored | scenarios not exhaustive | spent (USD) |", "|---|---|---|---|---|---|---|"]
    for r in runs:
        graded = [v for _, v in r["trials"].values() if v]
        secs = sorted((v.get("api") or {}).get("seconds") or 0 for v in graded)
        med = secs[len(secs) // 2] if secs else 0
        scs = [s for v in graded for s in v.get("scenarios") or []]
        meta = r["meta"]
        calls = meta.get("api_calls") if meta.get("api_calls") is not None else sum(
            s.get("calls", s.get("api_calls", 0)) for s in meta.get("sessions", []))
        out.append(f"| `{r['model']['id']}` | {calls} | {med:.0f} | {sum(v.get('seconds', 0) for v in graded):.0f} | "
                   f"{sum(s['schedules'] for s in scs)} | {sum(1 for s in scs if not s.get('exhaustive'))} of {len(scs)} | "
                   f"{meta.get('spent_usd', 0):.2f} |")
    vs = [_load(p) for p in RESULTS.glob("validation/*/*/verdict.json") if not p.parent.name.startswith("alt_")]
    out += ["", f"Grader validation (`make validate`, {len(vs)} solutions): "
            f"{sum(v.get('seconds', 0) for v in vs) / 60:.0f} min of grading time on the machine that produced these results "
            f"(sum of per-solution times; Docker Desktop on Windows 11)."]
    return "\n".join(out)


def sections() -> dict[str, str]:
    runs = final_runs()
    return {"models": models_section(runs), "results": results_section(runs),
            "failures": failures_section(runs), "validation": validation_section(),
            "runtime": runtime_section(runs)}


def write(readme: Path = README) -> list[str]:
    text = readme.read_text(encoding="utf-8")
    missing = []
    for name, body in sections().items():
        pat = re.compile(rf"(<!-- BEGIN report:{name} -->)\n.*?(<!-- END report:{name} -->)", re.S)
        if not pat.search(text):
            missing.append(name)
            continue
        text = pat.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)
    readme.write_text(text, encoding="utf-8", newline="\n")
    return missing


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--write", action="store_true", help="update README.md in place")
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if args.write:
        missing = write()
        print("README.md updated" + (f"; no markers for: {', '.join(missing)}" if missing else ""))
        return 1 if missing else 0
    for name, body in sections().items():
        print(f"## {name}\n\n{body}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
