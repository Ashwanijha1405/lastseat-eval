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
