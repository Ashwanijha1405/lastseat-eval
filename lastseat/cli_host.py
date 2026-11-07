"""Ask Claude through the official Claude Code CLI (`claude -p`), on the host.

    python lastseat/cli_host.py results/<run_id>

Runs on Windows/macOS/Linux outside Docker (the CLI and its login live on the
host), so it uses only the standard library and imports nothing from lastseat.
`python -m lastseat.official_cli prepare` (in Docker) writes the run folder
and each trial's prompt.txt first; `... grade` grades the answers afterwards.

Per call:
- a new empty temporary directory is the working directory (never this repo),
  and it must still be empty afterwards;
- every built-in tool is disabled (--tools ""), customizations are off
  (--safe-mode, --strict-mcp-config, --disable-slash-commands), nothing is saved
  (--no-session-persistence); the answer is text only;
- the child environment drops ANTHROPIC_*, CLAUDE*, and this project's keys, so
  the CLI uses its own claude.ai login, which is checked before every call;
- calls run one at a time; any error, usage-limit message or timeout stops the
  run without a verdict, so the cell stays missing and can be asked again.

The CLI adds its own system prompt; run_meta.json records that.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CALL_TIMEOUT_S = 30 * 60
DROP_ENV = re.compile(r"^(ANTHROPIC_|CLAUDE|OPENROUTER_|GEMINI_|GOOGLE_API_KEY$|LASTSEAT_)", re.IGNORECASE)
LIMIT_TEXT = re.compile(r"usage limit|limit reached|hit your (usage |session |weekly )?limit|rate[ _-]?limit"
                        r"|out of (extra )?usage|credit balance|quota", re.IGNORECASE)
SYSTEM_PROMPT_NOTE = ("Answers come from Claude Code headless mode (claude -p). The CLI's own system prompt is "
                      "included before the task prompt, so these cells are not directly comparable with "
                      "API/OpenRouter cells.")


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def child_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """The host environment minus anything that could change auth, routing or leak a key."""
    return {k: v for k, v in (os.environ if env is None else env).items() if not DROP_ENV.match(k)}


def claude_exe() -> str:
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("claude CLI not found on PATH")
    return exe


def cli_command(exe: str, model: str, effort: str) -> list[str]:
    return [exe, "-p", "--model", model, "--effort", effort, "--output-format", "json",
            "--tools", "", "--safe-mode", "--strict-mcp-config", "--disable-slash-commands",
            "--no-session-persistence"]


def cli_version(exe: str) -> str:
    out = subprocess.run([exe, "--version"], capture_output=True, text=True, encoding="utf-8",
                         env=child_env(), timeout=60)
    return out.stdout.strip()


def auth_problem(status: dict) -> str | None:
    """None when the CLI is logged in to claude.ai first-party (a subscription, no API billing)."""
    if not status.get("loggedIn"):
        return "the claude CLI is not logged in"
    if status.get("authMethod") != "claude.ai" or status.get("apiProvider") != "firstParty":
        return (f"refusing: the CLI would authenticate with authMethod={status.get('authMethod')!r}, "
                f"apiProvider={status.get('apiProvider')!r}; only a claude.ai login (subscription) is allowed")
    return None


def auth_status(exe: str) -> dict:
    out = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                         env=child_env(), timeout=60)
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {}


def classify(returncode: int, stdout: str, stderr: str) -> tuple[dict | None, str | None]:
    """(parsed result, None) for a usable answer, or (parsed-or-None, why the run must stop)."""
    try:
        result = json.loads(stdout)
    except ValueError:
        result = None
    text = (result or {}).get("result") if isinstance(result, dict) else None
    blob = f"{stdout}\n{stderr}"
    if result is None or not isinstance(result, dict):
        kind = "usage_limit" if LIMIT_TEXT.search(blob) else "cli_error"
        return None, f"{kind}: exit {returncode}: {blob.strip()[:500]}"
    if returncode != 0 or result.get("is_error") or result.get("subtype") != "success":
        kind = "usage_limit" if LIMIT_TEXT.search(blob) else "cli_error"
        return result, f"{kind}: exit {returncode}, subtype {result.get('subtype')}: {str(text)[:500]}"
    # A limit notice can arrive as a short plain "result"; a real answer has a code block.
    if isinstance(text, str) and len(text) < 400 and "```" not in text and LIMIT_TEXT.search(text):
        return result, f"usage_limit: {text.strip()}"
    if not isinstance(text, str) or not text.strip():
        return result, "cli_error: empty result"
    return result, None


def models_shown(result: dict) -> list[str]:
    return sorted((result.get("modelUsage") or {}).keys())


def ask_one(exe: str, cmd: list[str], prompt: str) -> tuple[subprocess.CompletedProcess | None, str | None, float]:
    """Run one call in a fresh empty directory. (process, problem, seconds)."""
    work = Path(tempfile.mkdtemp(prefix="lastseat-cli-"))
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                              cwd=work, env=child_env(), timeout=CALL_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, f"timeout after {CALL_TIMEOUT_S} s", time.monotonic() - start
    seconds = time.monotonic() - start
    left = sorted(p.name for p in work.iterdir())
    shutil.rmtree(work, ignore_errors=True)
    if left:
        return proc, f"cli_wrote_files: the CLI created {left} in its empty working directory", seconds
    return proc, None, seconds


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run(run_dir: Path) -> int:
    meta_file = run_dir / "run_meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    if meta.get("source") != "official-cli":
        print(f"{run_dir} is not an official-cli run")
        return 2
    exe = claude_exe()
    version = cli_version(exe)
    [model] = meta["models"]
    cmd = cli_command(exe, model["id"], meta["cli"]["effort"])
    trials = [run_dir / model["slug"] / t / f"trial_{n}" for t in meta["tasks"] for n in range(1, meta["trials"] + 1)]
    todo = [d for d in trials if not (d / "cli_response.json").exists()]
    print(f"official-cli run {run_dir.name}: {len(trials) - len(todo)} of {len(trials)} answered, "
          f"{len(todo)} to ask, sequentially; CLI {version}")
    session = {"started_utc": now_utc(), "cli_version": version, "calls": 0}
    meta.setdefault("sessions", []).append(session)
    meta["cli"].update({"version": version, "command": [Path(cmd[0]).name, *cmd[1:]],
                        "system_prompt_note": SYSTEM_PROMPT_NOTE,
                        "env_dropped": "ANTHROPIC_*, CLAUDE*, OPENROUTER_*, GEMINI_*, GOOGLE_API_KEY, LASTSEAT_*"})
    write_json(meta_file, meta)
    stopped = None
    for d in todo:
        cell = d.relative_to(run_dir).as_posix()
        problem = auth_problem(auth_status(exe))
        if problem:
            stopped = problem
            break
        prompt = (d / "prompt.txt").read_text(encoding="utf-8")
        started = now_utc()
        proc, problem, seconds = ask_one(exe, cmd, prompt)
        session["calls"] += 1
        result, why = (None, problem) if proc is None else classify(proc.returncode, proc.stdout, proc.stderr)
        why = problem or why
        if proc is not None:
            (d / "raw_cli_stdout.txt").write_text(proc.stdout, encoding="utf-8")
            if proc.stderr:
                (d / "raw_cli_stderr.txt").write_text(proc.stderr, encoding="utf-8")
        if why:
            # Not the model's answer: no verdict, the cell stays missing.
            (d / "api_error.txt").write_text(why + "\n", encoding="utf-8")
            stopped = f"{cell}: {why}"
            break
        (d / "api_error.txt").unlink(missing_ok=True)
        (d / "raw_response.txt").write_text(result["result"], encoding="utf-8")
        write_json(d / "cli_response.json", result)
        usage = result.get("usage") or {}
        write_json(d / "api.json", {
            "source": "official-cli", "model_id": model["id"], "models_shown": models_shown(result),
            "cli_version": version, "date_utc": started, "finish_reason": result.get("stop_reason"),
            "completion_tokens": usage.get("output_tokens"), "prompt_tokens": usage.get("input_tokens"),
            "cost_usd": 0.0, "cli_reported_cost_usd": result.get("total_cost_usd"),
            "seconds": round(seconds, 2), "num_turns": result.get("num_turns"), "attempts": 1,
            "provider": "claude.ai (claude -p)"})
        print(f"  {cell}: answered in {seconds:.0f} s, model {models_shown(result)}, "
              f"{usage.get('output_tokens')} output tokens", flush=True)
        write_json(meta_file, meta)
    session["finished_utc"] = now_utc()
    if stopped:
        session["stopped_reason"] = stopped
        print(f"STOPPED: {stopped}")
    write_json(meta_file, meta)
    return 1 if stopped else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(run(Path(sys.argv[1])))
