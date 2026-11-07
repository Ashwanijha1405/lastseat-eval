"""official-cli provider (claude -p): command, environment, error handling, end to end with a fake CLI."""

import json
import sys

import pytest

from lastseat import cli_host, official_cli
from lastseat.summary import summarize
from lastseat.task import TASKS_DIR


def test_the_cli_gets_no_tools_no_customizations_and_keeps_its_own_system_prompt():
    cmd = cli_host.cli_command("claude", "claude-opus-5-5", "high")
    assert cmd[cmd.index("--tools") + 1] == ""          # "" disables every built-in tool
    for flag in ("-p", "--safe-mode", "--strict-mcp-config", "--disable-slash-commands",
                 "--no-session-persistence"):
        assert flag in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5"
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert "--system-prompt" not in cmd and "--bare" not in cmd   # --bare would need a paid API key


def test_child_environment_drops_auth_routing_and_keys():
    env = cli_host.child_env({"PATH": "x", "ANTHROPIC_API_KEY": "k", "ANTHROPIC_BASE_URL": "u", "CLAUDECODE": "1",
                              "CLAUDE_CODE_ENTRYPOINT": "e", "OPENROUTER_API_KEY": "k", "GEMINI_API_KEY": "k",
                              "LASTSEAT_MAX_COST_USD": "0", "USERPROFILE": "p"})
    assert env == {"PATH": "x", "USERPROFILE": "p"}


@pytest.mark.parametrize("status, ok", [
    ({"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty"}, True),
    ({"loggedIn": True, "authMethod": "api_key", "apiProvider": "firstParty"}, False),
    ({"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "bedrock"}, False),
    ({"loggedIn": False}, False),
    ({}, False),
])
def test_only_a_claude_ai_login_is_allowed(status, ok):
    assert (cli_host.auth_problem(status) is None) == ok


def _out(result, is_error=False, subtype="success"):
    return json.dumps({"type": "result", "subtype": subtype, "is_error": is_error, "result": result,
                       "modelUsage": {"claude-opus-5-5": {}}, "usage": {"output_tokens": 5}})


@pytest.mark.parametrize("rc, stdout, kind", [
    (0, _out("```python\n# retry on rate limit\n```"), None),            # an answer may mention limits
    (1, _out("Claude AI usage limit reached|1731", is_error=True), "usage_limit"),
    (0, _out("You've hit your session limit · resets 5am"), "usage_limit"),   # short notice, no code
    (1, "Error: something broke", "cli_error"),
    (1, "Usage limit reached", "usage_limit"),
    (0, _out("   "), "cli_error"),
    (0, _out("x", subtype="error_max_turns"), "cli_error"),
])
def test_classify_stops_on_errors_and_usage_limits(rc, stdout, kind):
    _, why = cli_host.classify(rc, stdout, "")
    assert (why is None) if kind is None else why.startswith(kind)


def test_a_cli_that_writes_into_its_directory_is_caught():
    cmd = [sys.executable, "-c", "open('x.txt','w').write('1'); print('{}')"]
    _, problem, _ = cli_host.ask_one("python", cmd, "prompt")
    assert problem and problem.startswith("cli_wrote_files")


FAKE_CLI = r'''
import json, sys
from pathlib import Path
prompt = sys.stdin.read()
assert "Concurrency contract" in prompt or len(prompt) > 500, "the prompt must arrive on stdin"
assert not any(Path(".").iterdir()), "must run in an empty directory"
mode = Path(sys.argv[1]).read_text()
if mode == "limit":
    print(json.dumps({"type": "result", "subtype": "success", "is_error": True,
                      "result": "Claude AI usage limit reached|1731"})); sys.exit(1)
code = Path(sys.argv[2]).read_text()
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
                  "result": "Here:\n```python\n" + code + "```\n", "stop_reason": "end_turn",
                  "total_cost_usd": 0.5, "usage": {"input_tokens": 10, "output_tokens": 20},
                  "modelUsage": {"claude-opus-5-5": {}}}))
'''


@pytest.fixture
def cli_run(tmp_path, monkeypatch):
    results = tmp_path / "results"
    results.mkdir()
    monkeypatch.setattr(official_cli, "RESULTS", results)
    fake, mode = tmp_path / "fake_claude.py", tmp_path / "mode"
    fake.write_text(FAKE_CLI, encoding="utf-8")
    mode.write_text("answer")
    ref = TASKS_DIR / "t01_flash_sale" / "reference.py"
    monkeypatch.setattr(cli_host, "claude_exe", lambda: "claude")
    monkeypatch.setattr(cli_host, "cli_version", lambda exe: "9.9.9 (Claude Code)")
    monkeypatch.setattr(cli_host, "auth_status",
                        lambda exe: {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty"})
    monkeypatch.setattr(cli_host, "cli_command", lambda exe, model, effort: [sys.executable, str(fake), str(mode),
                                                                             str(ref)])
    assert official_cli.main(["prepare", "--run-id", "c", "--model", "claude-opus-5-5", "--slug", "opus",
                              "--trials", "2", "--task", "t01_flash_sale"]) == 0
    return results / "c", mode


def test_end_to_end_with_a_fake_cli_records_the_source_and_grades(cli_run):
    run_dir, _ = cli_run
    assert cli_host.run(run_dir) == 0
    assert official_cli.grade(run_dir) == 0
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["source"] == "official-cli" and meta["complete"] is True and meta["api_calls"] == 2
    assert meta["cli"]["version"] == "9.9.9 (Claude Code)" and "system prompt" in meta["cli"]["system_prompt_note"]
    v = json.loads((run_dir / "opus" / "t01_flash_sale" / "trial_1" / "verdict.json").read_text(encoding="utf-8"))
    assert v["passed"] is True
    assert v["api"]["models_shown"] == ["claude-opus-5-5"] and v["api"]["cost_usd"] == 0.0
    text = summarize(run_dir)
    assert "## Source: official-cli" in text and "pass^2: yes" in text and "9.9.9" in text


def test_a_usage_limit_stops_the_run_without_a_verdict(cli_run):
    run_dir, mode = cli_run
    mode.write_text("limit")
    assert cli_host.run(run_dir) == 1
    t1 = run_dir / "opus" / "t01_flash_sale" / "trial_1"
    assert "usage_limit" in (t1 / "api_error.txt").read_text(encoding="utf-8")
    assert not (t1 / "cli_response.json").exists()
    assert not (run_dir / "opus" / "t01_flash_sale" / "trial_2" / "raw_cli_stdout.txt").exists(), "must stop"
    official_cli.grade(run_dir)
    assert not (t1 / "verdict.json").exists()
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert "usage_limit" in meta["sessions"][-1]["stopped_reason"] and meta["complete"] is False

    mode.write_text("answer")            # the same command later asks the missing cells
    assert cli_host.run(run_dir) == 0 and not (t1 / "api_error.txt").exists()


def test_prepare_never_starts_a_run_implicitly(cli_run, capsys):
    assert official_cli.main(["prepare", "--model", "m", "--task", "t01_flash_sale"]) == 2
    assert official_cli.main(["prepare", "--run-id", "c", "--model", "other", "--slug", "opus",
                              "--trials", "2", "--task", "t01_flash_sale"]) == 2   # a different signature


# --- Antigravity CLI (agy), for Gemini -----------------------------------------

def _agy_out(response="```python\nx = 1\n```", status="SUCCESS", tools=(), error=None):
    ev = [{"event": "init", "init": {"model": "gemini-3.8-flash-high"}}]
    for name, state in tools:
        ev.append({"event": "step_update", "step_update": {"step_type": "tool", "state": state, "tool_name": name}})
    res = {"status": status, "response": response, "num_turns": 1,
           "usage": {"input_tokens": 9, "output_tokens": 7, "thinking_tokens": 3}}
    if error:
        res["error"] = error
    ev.append({"event": "result", "result": res})
    return "\n".join(json.dumps(e) for e in ev) + "\n"


def test_agy_denies_every_tool_namespace_and_reads_the_prompt_from_stdin():
    cmd = cli_host.agy_command("agy", "gemini-3.8-flash-high")
    settings = json.loads(cmd[cmd.index("--settings") + 1])
    assert set(settings["permissions"]["deny"]) == {f"{a}(*)" for a in (
        "read_file", "write_file", "command", "unsandboxed", "read_url", "execute_url", "mcp")}
    assert settings["permissions"]["allow"] == [] and settings["toolPermission"] == "strict"
    assert cmd[cmd.index("--input-format") + 1] == "stream-json" and cmd[cmd.index("--print") + 1] == ""
    assert "--dangerously-skip-permissions" not in cmd
    assert json.loads(cli_host.agy_stdin("hello")) == {"event": "user", "message": {"content": "hello"}}


@pytest.mark.parametrize("rc, stdout, stderr, kind", [
    (0, _agy_out(), "", None),
    (0, _agy_out(tools=[("run_command", "ERROR"), ("write_file", "ERROR")]), "", None),   # denied: still graded
    (0, _agy_out(tools=[("view_file", "DONE")]), "", "tool_ran"),
    (1, _agy_out(status="ERROR", response="", error="RESOURCE_EXHAUSTED: quota exceeded"), "", "usage_limit"),
    (1, "", "Error: authentication required", "cli_error"),
    (1, "", "429 Too Many Requests", "usage_limit"),
    (0, _agy_out(response="You have reached your daily quota."), "", "usage_limit"),
    (0, _agy_out(response=" "), "", "cli_error"),
])
def test_agy_classify(rc, stdout, stderr, kind):
    fields, why = cli_host.agy_classify(rc, stdout, stderr)
    assert (why is None) if kind is None else why.startswith(kind)
    if kind is None:
        assert fields["models_shown"] == ["gemini-3.8-flash-high"] and fields["output_tokens"] == 7


def test_agy_refuses_an_api_key_model_provider(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"model": "Gemini 3.8 Flash (High)"}), encoding="utf-8")
    assert cli_host.agy_preflight(f) is None
    f.write_text(json.dumps({"modelProvider": "gemini"}), encoding="utf-8")
    assert "modelProvider" in cli_host.agy_preflight(f)


def test_child_environment_drops_google_keys_and_cloud_settings():
    env = cli_host.child_env({"PATH": "x", "GOOGLE_API_KEY": "k", "GOOGLE_GENAI_USE_VERTEXAI": "1",
                              "GOOGLE_CLOUD_PROJECT": "p", "GOOGLE_APPLICATION_CREDENTIALS": "c",
                              "GEMINI_API_KEY": "k", "APPDATA": "a"})
    assert env == {"PATH": "x", "APPDATA": "a"}


FAKE_AGY = r'''
import json, sys
from pathlib import Path
event = json.loads(sys.stdin.readline())
assert event["event"] == "user" and len(event["message"]["content"]) > 500, "prompt must arrive on stdin"
assert not any(Path(".").iterdir()), "must run in an empty directory"
code = Path(sys.argv[1]).read_text()
print(json.dumps({"event": "init", "init": {"model": "gemini-3.8-flash-high"}}))
print(json.dumps({"event": "step_update", "step_update": {"step_type": "tool", "state": "ERROR", "tool_name": "view_file"}}))
print(json.dumps({"event": "result", "result": {"status": "SUCCESS", "num_turns": 1,
      "response": "```python\n" + code + "```\n", "usage": {"input_tokens": 10, "output_tokens": 20}}}))
'''


def test_end_to_end_with_a_fake_agy(tmp_path, monkeypatch):
    results = tmp_path / "results"
    results.mkdir()
    monkeypatch.setattr(official_cli, "RESULTS", results)
    fake = tmp_path / "fake_agy.py"
    fake.write_text(FAKE_AGY, encoding="utf-8")
    ref = TASKS_DIR / "t01_flash_sale" / "reference.py"
    monkeypatch.setattr(cli_host, "agy_exe", lambda: "agy")
    monkeypatch.setattr(cli_host, "cli_version", lambda exe: "1.4.12")
    monkeypatch.setattr(cli_host, "agy_preflight", lambda: None)
    monkeypatch.setattr(cli_host, "agy_command", lambda exe, model: [sys.executable, str(fake), str(ref)])
    assert official_cli.main(["prepare", "--run-id", "g", "--cli", "antigravity", "--model", "gemini-3.8-flash-high",
                              "--trials", "1", "--task", "t01_flash_sale"]) == 0
    run_dir = results / "g"
    assert cli_host.run(run_dir) == 0 and official_cli.grade(run_dir) == 0
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["config"] == "official-cli:antigravity" and meta["cli"]["name"] == "antigravity"
    assert "Antigravity" in meta["cli"]["system_prompt_note"]
    v = json.loads((run_dir / "gemini-3.8-flash-high" / "t01_flash_sale" / "trial_1" / "verdict.json")
                   .read_text(encoding="utf-8"))
    assert v["passed"] is True and v["api"]["tool_calls_denied"] == 1 and v["api"]["cli"] == "antigravity"


@pytest.mark.parametrize("why, transient", [
    ("cli_error: exit 0, status ERROR: The stream was interrupted. Please continue the task", True),
    ("cli_error: exit 1, status ERROR: 503 UNAVAILABLE", True),
    ("usage_limit: exit 1, status ERROR: RESOURCE_EXHAUSTED", False),     # a limit stops at once
    ("tool_ran: the CLI ran ['view_file']", False),
    ("timeout after 1800 s", False),
    ("cli_error: exit 1, no result event: Error: authentication required", False),
])
def test_only_transient_cli_errors_are_retried(why, transient):
    assert cli_host.is_transient(why) == transient


FLAKY_AGY = r'''
import json, sys
from pathlib import Path
sys.stdin.readline()
count = Path(sys.argv[2]); n = int(count.read_text()) + 1; count.write_text(str(n))
if n == 1:
    print(json.dumps({"event": "result", "result": {"status": "ERROR", "response": "partial ```python\nx=1\n```",
          "error": "The stream was interrupted. Please continue the task you were working on."}}))
    sys.exit(0)
code = Path(sys.argv[1]).read_text()
print(json.dumps({"event": "init", "init": {"model": "gemini-3.8-flash-high"}}))
print(json.dumps({"event": "result", "result": {"status": "SUCCESS", "num_turns": 1,
      "response": "```python\n" + code + "```\n", "usage": {"input_tokens": 10, "output_tokens": 20}}}))
'''


def test_a_transient_error_is_retried_and_the_error_answer_is_never_graded(tmp_path, monkeypatch):
    results = tmp_path / "results"
    results.mkdir()
    monkeypatch.setattr(official_cli, "RESULTS", results)
    fake, count = tmp_path / "flaky_agy.py", tmp_path / "count"
    fake.write_text(FLAKY_AGY, encoding="utf-8")
    count.write_text("0")
    ref = TASKS_DIR / "t01_flash_sale" / "reference.py"
    monkeypatch.setattr(cli_host, "agy_exe", lambda: "agy")
    monkeypatch.setattr(cli_host, "cli_version", lambda exe: "1.5.3")
    monkeypatch.setattr(cli_host, "agy_preflight", lambda: None)
    monkeypatch.setattr(cli_host, "agy_command", lambda exe, model: [sys.executable, str(fake), str(ref), str(count)])
    assert official_cli.main(["prepare", "--run-id", "f", "--cli", "antigravity", "--model", "gemini-3.8-flash-high",
                              "--trials", "1", "--task", "t01_flash_sale"]) == 0
    run_dir = results / "f"
    assert cli_host.run(run_dir) == 0 and count.read_text() == "2"
    t1 = run_dir / "gemini-3.8-flash-high" / "t01_flash_sale" / "trial_1"
    assert (t1 / "raw_cli_stdout.attempt1.txt").exists()
    assert "x=1" not in (t1 / "raw_response.txt").read_text(encoding="utf-8")   # the second answer is graded
    api = json.loads((t1 / "api.json").read_text(encoding="utf-8"))
    assert api["attempts"] == 2
