"""Ask a model through an official vendor CLI, on the host: Claude Code
(`claude -p`) or, for Gemini, Antigravity CLI (`agy --print`).

    python lastseat/cli_host.py results/<run_id>

Runs on Windows/macOS/Linux outside Docker (the CLI and its login live on the
host), so it uses only the standard library and imports nothing from lastseat.
`python -m lastseat.official_cli prepare` (in Docker) writes the run folder
and each trial's prompt.txt first; `... grade` grades the answers afterwards.

Per call, both CLIs:
- a new empty temporary directory is the working directory (never this repo),
  and it must still be empty afterwards;
- the prompt goes on stdin; the child environment drops ANTHROPIC_*, CLAUDE*,
  GEMINI_*, GOOGLE_* keys/cloud settings and this project's keys, so the CLI
  uses its own subscription / free sign-in, which is checked before every call;
- calls run one at a time; any error, usage-limit message or timeout stops the
  run without a verdict, so the cell stays missing and can be asked again.

claude: every built-in tool is disabled (--tools ""), customizations are off
(--safe-mode, --strict-mcp-config, --disable-slash-commands), nothing is saved
(--no-session-persistence).
agy: no flag removes tools, so --settings denies every action namespace (deny
rules apply in every mode) with toolPermission strict; a tool that still runs
stops the run (tool_ran). Denied attempts are counted in api.json. A
modelProvider in the user's agy settings (API-key route) is refused.

Each CLI adds its own system prompt; run_meta.json records that.
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
MAX_ATTEMPTS = 3  # per cell, only for transient errors (as the OpenRouter runner retries transport errors)
# A server or stream hiccup, not the model's answer and not a usage limit: worth one more fresh call.
TRANSIENT = re.compile(r"stream was interrupted|overloaded|UNAVAILABLE|\b5\d\d\b|internal (server )?error"
                       r"|deadline exceeded|connection (reset|closed)", re.IGNORECASE)
# Anything that could change auth or routing (e.g. an API key would make Gemini a paid route) or leak a key.
DROP_ENV = re.compile(r"^(ANTHROPIC_|CLAUDE|OPENROUTER_|GEMINI_|GOOGLE_API_KEY$|GOOGLE_GENAI|GOOGLE_CLOUD"
                      r"|GOOGLE_APPLICATION_CREDENTIALS$|LASTSEAT_)", re.IGNORECASE)
LIMIT_TEXT = re.compile(r"usage limit|limit reached|hit your (usage |session |weekly )?limit|rate[ _-]?limit"
                        r"|out of (extra )?usage|credit balance|quota|RESOURCE_EXHAUSTED|exhausted|\b429\b",
                        re.IGNORECASE)
SYSTEM_PROMPT_NOTE = ("Answers come from Claude Code headless mode (claude -p). The CLI's own system prompt is "
                      "included before the task prompt, so these cells are not directly comparable with "
                      "API/OpenRouter cells.")
AGY_SYSTEM_PROMPT_NOTE = ("Answers come from Antigravity CLI print mode (agy --print), Google's CLI for free "
                          "personal accounts (it replaced Gemini CLI for them on 2026-06-18). Its own agent system "
                          "prompt and tool list are included (about 8.5k input tokens for a one-word prompt); every "
                          "tool action is denied by --settings, so it can only answer in text. Not directly "
                          "comparable with API/OpenRouter cells.")


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


def is_transient(why: str) -> bool:
    """True for cli_error reasons worth retrying; usage limits, tool runs and timeouts are not."""
    return why.startswith("cli_error") and bool(TRANSIENT.search(why))


def models_shown(result: dict) -> list[str]:
    return sorted((result.get("modelUsage") or {}).keys())


def claude_fields(result: dict) -> dict:
    usage = result.get("usage") or {}
    return {"text": result.get("result"), "models_shown": models_shown(result), "finish": result.get("stop_reason"),
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
            "reported_cost_usd": result.get("total_cost_usd"), "num_turns": result.get("num_turns")}


# --- Antigravity CLI (agy), for Gemini --------------------------------------
# Flags from `agy --help` (1.4.12) and antigravity.google/docs (cli/headless,
# permissions, settings). The prompt goes on stdin as one stream-json user
# event; --print "" turns on print mode (a flag prompt is dropped in this mode).
# Every tool action namespace is denied (deny rules apply in every mode), and
# strict mode asks before every action, which print mode cannot answer.
AGY_DENY = ["read_file(*)", "write_file(*)", "command(*)", "unsandboxed(*)", "read_url(*)", "execute_url(*)",
            "mcp(*)"]
AGY_SETTINGS = {"permissions": {"allow": [], "ask": [], "deny": AGY_DENY}, "toolPermission": "strict",
                "disableSlashCommands": True, "enableTerminalSandbox": True}
AGY_USER_SETTINGS = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"


def agy_exe() -> str:
    exe = shutil.which("agy")
    if not exe:
        raise SystemExit("agy (Antigravity CLI) not found on PATH")
    return exe


def agy_command(exe: str, model: str) -> list[str]:
    return [exe, "--print", "", "--input-format", "stream-json", "--output-format", "stream-json",
            "--model", model, "--settings", json.dumps(AGY_SETTINGS, separators=(",", ":")),
            "--disable-slash-commands", "--print-timeout", f"{CALL_TIMEOUT_S - 60}s"]


def agy_stdin(prompt: str) -> str:
    return json.dumps({"event": "user", "message": {"content": prompt}}) + "\n"


def agy_preflight(settings_file: Path | None = None) -> str | None:
    """None when agy will use the Google sign-in: a modelProvider (e.g. "gemini" = API key) could bill."""
    path = settings_file or AGY_USER_SETTINGS
    try:
        settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        return f"refusing: cannot read {path}"
    if settings.get("modelProvider"):
        return (f"refusing: {path} sets modelProvider={settings['modelProvider']!r}; only the Google sign-in "
                "(no modelProvider) is allowed")
    return None


def agy_classify(returncode: int, stdout: str, stderr: str) -> tuple[dict | None, str | None]:
    """(fields, None) for a usable answer, or (fields-or-None, why the run must stop)."""
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    init = next((e.get("init") or {} for e in events if e.get("event") == "init"), {})
    result = next((e.get("result") or {} for e in reversed(events) if e.get("event") == "result"), None)
    tools = [e["step_update"] for e in events
             if e.get("event") == "step_update" and (e.get("step_update") or {}).get("step_type") == "tool"
             and (e["step_update"].get("state") in ("DONE", "ERROR"))]
    ran = [t.get("tool_name") for t in tools if t.get("state") == "DONE"]
    blob = f"{stderr}\n{(result or {}).get('error') or ''}"
    if result is None:
        kind = "usage_limit" if LIMIT_TEXT.search(f"{stdout}\n{stderr}") else "cli_error"
        return None, f"{kind}: exit {returncode}, no result event: {(stderr or stdout).strip()[:500]}"
    usage = result.get("usage") or {}
    fields = {"text": result.get("response"), "models_shown": [init["model"]] if init.get("model") else [],
              "finish": result.get("status"), "input_tokens": usage.get("input_tokens"),
              "output_tokens": usage.get("output_tokens"), "thinking_tokens": usage.get("thinking_tokens"),
              "reported_cost_usd": None, "num_turns": result.get("num_turns"),
              "tool_calls_denied": sum(1 for t in tools if t.get("state") == "ERROR"), "tool_calls_ran": ran}
    if returncode != 0 or result.get("status") != "SUCCESS":
        kind = "usage_limit" if LIMIT_TEXT.search(blob) else "cli_error"
        return fields, f"{kind}: exit {returncode}, status {result.get('status')}: {blob.strip()[:500]}"
    if ran:
        return fields, f"tool_ran: the CLI ran {ran} although every tool action is denied"
    text = fields["text"]
    if isinstance(text, str) and len(text) < 400 and "```" not in text and LIMIT_TEXT.search(text):
        return fields, f"usage_limit: {text.strip()}"
    if not isinstance(text, str) or not text.strip():
        return fields, "cli_error: empty response"
    return fields, None


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
    [model] = meta["models"]
    name = meta["cli"].get("name", "claude")
    if name == "claude":
        exe = claude_exe()
        version = cli_version(exe)
        cmd = cli_command(exe, model["id"], meta["cli"]["effort"])
        stdin_of, note = (lambda p: p), SYSTEM_PROMPT_NOTE
        preflight = lambda: auth_problem(auth_status(exe))  # noqa: E731

        def parse(rc, out, err):
            result, why = classify(rc, out, err)
            return (claude_fields(result) if isinstance(result, dict) else None), why, result
    elif name == "antigravity":
        exe = agy_exe()
        version = cli_version(exe)
        cmd = agy_command(exe, model["id"])
        stdin_of, note, preflight = agy_stdin, AGY_SYSTEM_PROMPT_NOTE, agy_preflight

        def parse(rc, out, err):
            fields, why = agy_classify(rc, out, err)
            return fields, why, {"fields": fields}
    else:
        print(f"unknown cli {name!r}")
        return 2
    trials = [run_dir / model["slug"] / t / f"trial_{n}" for t in meta["tasks"] for n in range(1, meta["trials"] + 1)]
    todo = [d for d in trials if not (d / "cli_response.json").exists()]
    print(f"official-cli run {run_dir.name}: {len(trials) - len(todo)} of {len(trials)} answered, "
          f"{len(todo)} to ask, sequentially; CLI {version}")
    session = {"started_utc": now_utc(), "cli_version": version, "calls": 0}
    meta.setdefault("sessions", []).append(session)
    meta["cli"].update({"version": version, "command": [Path(cmd[0]).name, *cmd[1:]],
                        "system_prompt_note": note,
                        "env_dropped": "ANTHROPIC_*, CLAUDE*, OPENROUTER_*, GEMINI_*, GOOGLE_API_KEY, GOOGLE_GENAI*, "
                                       "GOOGLE_CLOUD*, GOOGLE_APPLICATION_CREDENTIALS, LASTSEAT_*"})
    write_json(meta_file, meta)
    provider = {"claude": "claude.ai (claude -p)", "antigravity": "Google sign-in (agy --print)"}[name]
    stopped = None
    for d in todo:
        cell = d.relative_to(run_dir).as_posix()
        problem = preflight()
        if problem:
            stopped = problem
            break
        prompt = (d / "prompt.txt").read_text(encoding="utf-8")
        started = now_utc()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            proc, problem, seconds = ask_one(exe, cmd, stdin_of(prompt))
            session["calls"] += 1
            fields, why, raw = ((None, problem, None) if proc is None
                                else parse(proc.returncode, proc.stdout, proc.stderr))
            why = problem or why
            if not (why and is_transient(why)) or attempt == MAX_ATTEMPTS:
                break
            # A transient CLI/server error: keep its output, ask again as a fresh call.
            if proc is not None:
                (d / f"raw_cli_stdout.attempt{attempt}.txt").write_text(proc.stdout, encoding="utf-8")
            print(f"  {cell}: attempt {attempt} hit a transient error, retrying: {why[:160]}", flush=True)
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
        (d / "raw_response.txt").write_text(fields["text"], encoding="utf-8")
        write_json(d / "cli_response.json", raw)
        api = {"source": "official-cli", "cli": name, "model_id": model["id"], "models_shown": fields["models_shown"],
               "cli_version": version, "date_utc": started, "finish_reason": fields["finish"],
               "completion_tokens": fields["output_tokens"], "prompt_tokens": fields["input_tokens"],
               "cost_usd": 0.0, "cli_reported_cost_usd": fields["reported_cost_usd"],
               "seconds": round(seconds, 2), "num_turns": fields["num_turns"], "attempts": attempt, "provider": provider}
        for k in ("thinking_tokens", "tool_calls_denied", "tool_calls_ran"):
            if k in fields:
                api[k] = fields[k]
        write_json(d / "api.json", api)
        print(f"  {cell}: answered in {seconds:.0f} s, model {fields['models_shown']}, "
              f"{fields['output_tokens']} output tokens"
              + (f", {fields['tool_calls_denied']} tool call(s) denied" if fields.get("tool_calls_denied") else ""),
              flush=True)
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
