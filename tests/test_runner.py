"""Runner: code extraction, retries, cost guard, refusal rules, dry-run pipeline. No network."""

import http.client
import json
import shutil
import time
import uuid

import pytest

from lastseat import runner
from lastseat.runner import (ApiError, Budget, Job, Model, OpenRouterClient, RunState, TransportError,
                             extract_code)
from lastseat.task import TASKS_DIR, load_task

MODEL = Model("m", "lab/model")


def test_extract_takes_the_last_python_block():
    text = "draft:\n```python\nx = 1\n```\nfinal:\n```Python\r\ndef f(db):\n    return 2\n```\nbye"
    assert extract_code(text) == "def f(db):\n    return 2\n"


@pytest.mark.parametrize("text", ["no code at all", "```\ndef f(): pass\n```", "```py\ndef f(): pass\n```", ""])
def test_extract_requires_a_python_fence(text):
    assert extract_code(text) is None


def _client(responses, **kw):
    client = OpenRouterClient("sk-test", {"max_tokens": 10}, {MODEL.id: (1e-6, 2e-6)}, sleep=lambda s: None, **kw)
    calls = []

    def fake_post(payload):
        calls.append(json.loads(payload))
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    client._post = fake_post
    return client, calls


OK = {"model": "lab/model", "choices": [{"message": {"content": "hi"}}],
      "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.0123}}


def test_transport_errors_are_retried_with_the_same_request():
    client, calls = _client([TransportError("HTTP 429"), TransportError("HTTP 502"), OK])
    reply = client.complete(MODEL, "prompt")

    assert reply.attempts == 3 and reply.cost_usd == 0.0123
    assert calls[0] == calls[1] == calls[2]
    assert calls[0]["model"] == "lab/model" and calls[0]["max_tokens"] == 10
    assert "temperature" not in calls[0]


def test_rejected_requests_are_not_retried():
    client, calls = _client([ApiError("HTTP 400"), OK])
    with pytest.raises(ApiError):
        client.complete(MODEL, "prompt")
    assert len(calls) == 1


def test_cost_falls_back_to_list_prices():
    no_cost = {**OK, "usage": {"prompt_tokens": 100, "completion_tokens": 50}}
    client, _ = _client([no_cost])
    assert client.complete(MODEL, "p").cost_usd == pytest.approx(100 * 1e-6 + 50 * 2e-6)


def test_budget_stops_before_a_call_that_could_exceed_it(tmp_path):
    task = load_task(TASKS_DIR / "t01_flash_sale")
    client, calls = _client([OK])
    state = RunState(tmp_path, {}, Budget(max_usd=1.0, spent_usd=0.95))

    solution = runner.ask(client, Job(MODEL, task, 1, tmp_path / "t"), state, worst_case_usd=0.10)

    assert solution is None and calls == []
    assert state.budget.stopped_reason.startswith("budget:")


def test_paid_run_is_refused_until_models_are_confirmed(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "models.yaml"
    cfg.write_text("confirmed: false\nsettings: {}\nmodels:\n  - {slug: m, id: lab/model}\n", encoding="utf-8")
    monkeypatch.setattr(runner, "fetch_catalog", lambda: pytest.fail("must not touch the network"))

    assert runner.main(["run", "--trials", "1", "--yes", "--task", "t01_flash_sale", "--config", str(cfg)]) == 2
    assert "confirmed: false" in capsys.readouterr().out


# --- free tier: zero spend is enforced in code --------------------------------

FREE_ID = "lab/model:free"
ZERO = {"prompt": "0", "completion": "0", "request": "0", "image": "0"}


def _free_config(tmp_path, ids=(FREE_ID,), settings="{max_tokens: 10}"):
    cfg = tmp_path / "models.free.yaml"
    models = "".join(f"  - {{slug: m{i}, id: '{mid}'}}\n" for i, mid in enumerate(ids))
    cfg.write_text(f"tier: free\nconfirmed: true\nsettings: {settings}\nmodels:\n{models}", encoding="utf-8")
    return cfg


def test_shipped_configs_are_the_free_default_and_the_paid_set():
    assert runner.load_models().free and runner.load_models().path.name == "models.free.yaml"
    assert runner.load_models(runner.config_path("paid")).tier == "paid"
    assert all(m.id.endswith(":free") for m in runner.load_models().models)


@pytest.mark.parametrize("ids,settings,message", [
    ((FREE_ID, "lab/model"), "{}", "do not end in ':free'"),
    ((FREE_ID,), "{provider: {max_price: {prompt: 5}}}", "may not set 'provider'"),
])
def test_free_config_rejects_paid_ids_and_price_overrides(tmp_path, ids, settings, message):
    with pytest.raises(ValueError, match=message):
        runner.load_models(_free_config(tmp_path, ids, settings))


def test_free_run_refuses_a_positive_cost_limit(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("LASTSEAT_MAX_COST_USD", "5")
    monkeypatch.setattr(runner, "fetch_catalog", lambda: pytest.fail("must not touch the network"))
    argv = ["run", "--trials", "1", "--yes", "--task", "t01_flash_sale", "--config", str(_free_config(tmp_path))]
    assert runner.main(argv) == 2
    assert "capped at $0" in capsys.readouterr().out


def test_free_run_refuses_a_model_the_catalog_prices_above_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("LASTSEAT_MAX_COST_USD", "0")
    monkeypatch.setattr(runner, "fetch_catalog", lambda: {FREE_ID: {"id": FREE_ID,
                                                                     "pricing": {**ZERO, "request": "0.001"}}})
    monkeypatch.setattr(OpenRouterClient, "_post", lambda self, p: pytest.fail("must not call the model"))
    argv = ["run", "--trials", "1", "--yes", "--task", "t01_flash_sale", "--config", str(_free_config(tmp_path))]
    assert runner.main(argv) == 2
    assert "nonzero price" in capsys.readouterr().out


@pytest.fixture
def free_env(tmp_path, monkeypatch):
    """A free run with no network, no real sleeping, and results/ (and the quota file) in tmp."""
    results = tmp_path / "results"
    results.mkdir()
    monkeypatch.setattr(runner, "RESULTS", results)
    monkeypatch.setattr(runner, "_sleep", lambda s: None)
    monkeypatch.setattr(runner, "fetch_key_status", lambda key: None)
    monkeypatch.setattr(runner, "fetch_catalog", lambda: {FREE_ID: {"id": FREE_ID, "pricing": ZERO}})
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("LASTSEAT_MAX_COST_USD", "0")
    return results


def _fake_post(monkeypatch, responses):
    sent = []

    def fake_post(self, payload):
        sent.append(json.loads(payload))
        r = responses.pop(0) if len(responses) > 1 else responses[0]  # the last response repeats
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(OpenRouterClient, "_post", fake_post)
    return sent


TWO_TASKS = ["--task", "t01_flash_sale", "--task", "t02_on_call"]
FREE_OK = {**OK, "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}}


def test_free_run_caps_the_price_and_stops_on_any_reported_cost(tmp_path, monkeypatch, free_env):
    monkeypatch.delenv("LASTSEAT_MAX_COST_USD", raising=False)
    sent = _fake_post(monkeypatch, [{**OK, "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0001}}])
    argv = ["run", "--trials", "1", "--yes", *TWO_TASKS, "--config", str(_free_config(tmp_path)), "--run-id", "r"]
    assert runner.main(argv) == 1
    assert len(sent) == 1, "the run must stop after the first reply that reports a cost"
    assert sent[0]["provider"] == {"max_price": {"prompt": 0, "completion": 0, "request": 0, "image": 0}}
    meta = json.loads((free_env / "r" / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["tier"] == "free" and meta["budget_limit_usd"] == 0.0
    assert "reported cost" in meta["stopped_reason"]  # stopped right after the reply, not at the next call


# --- free tier: rate limit, daily quota, resume --------------------------------


def test_rate_limiter_spaces_request_starts():
    now, slept = [100.0], []

    def sleep(s):
        slept.append(s)
        now[0] += s

    limiter = runner.RateLimiter(4.0, clock=lambda: now[0], sleep=sleep)
    limiter.wait()          # first request: no wait
    now[0] += 1.0
    limiter.wait()          # 1 s later: waits the remaining 3 s
    now[0] += 10.0
    limiter.wait()          # 10 s later: no wait
    assert slept == [pytest.approx(3.0)]


def test_daily_quota_persists_refuses_at_the_limit_and_resets_each_utc_day(tmp_path):
    path, day = tmp_path / "q.json", ["2026-11-06"]
    quota = runner.DailyQuota(path, 3, today=lambda: day[0])
    for _ in range(3):
        quota.take()
    again = runner.DailyQuota(path, 3, today=lambda: day[0])  # a later run reads the same file
    assert again.used() == 3 and again.remaining() == 0
    with pytest.raises(runner.QuotaExhausted, match="3 of 3"):
        again.take()
    day[0] = "2026-11-07"
    assert again.remaining() == 3


def test_quota_adopts_openrouters_count_when_it_is_higher(tmp_path):
    quota = runner.DailyQuota(tmp_path / "q.json", 50)
    quota.take()
    quota.sync({"used": 12, "limit": 50, "remaining": 38})
    assert quota.used() == 12
    quota.sync({"used": 3, "limit": 20, "remaining": 17})  # lower server count never lowers ours
    assert quota.used() == 12 and quota.limit == 20


def _gated_client(tmp_path, responses, limit=50):
    quota = runner.DailyQuota(tmp_path / "q.json", limit)
    client, calls = _client(responses, max_attempts=4)
    client.gate = runner.FreeGate(quota, runner.RateLimiter(0, sleep=lambda s: None))
    return client, calls, quota


def test_per_minute_429_is_retried_and_every_attempt_is_counted(tmp_path):
    minute = runner._rate_limit_error(429, {"Retry-After": "7"}, '{"error":{"code":429}}')
    client, calls, quota = _gated_client(tmp_path, [minute, minute, OK])
    waits = []
    client._sleep = waits.append
    assert client.complete(MODEL, "p").attempts == 3
    assert len(calls) == 3 and quota.used() == 3
    assert all(7 <= w < 8 for w in waits)  # Retry-After honoured


def test_daily_429_is_not_retried(tmp_path):
    reset_ms = str((time.time() + 6 * 3600) * 1000)
    daily = runner._rate_limit_error(429, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": reset_ms}, "{}")
    client, calls, _ = _gated_client(tmp_path, [daily, OK])
    with pytest.raises(TransportError) as e:
        client.complete(MODEL, "p")
    assert e.value.daily_exhausted and len(calls) == 1


def test_rate_limit_stops_without_a_verdict_and_the_same_command_resumes(tmp_path, monkeypatch, free_env, capsys):
    minute = runner._rate_limit_error(429, {}, "Rate limit exceeded")
    sent = _fake_post(monkeypatch, [FREE_OK, minute])
    argv = ["run", "--trials", "1", "--yes", *TWO_TASKS, "--config", str(_free_config(tmp_path))]

    assert runner.main(argv + ["--new"]) == 1
    [first] = [p for p in free_env.iterdir() if p.is_dir()]
    run_dir = first.rename(free_env / "an-earlier-run")  # so a fresh timestamped run could not land on it
    t01, t02 = run_dir / "m0" / "t01_flash_sale" / "trial_1", run_dir / "m0" / "t02_on_call" / "trial_1"
    assert (t01 / "verdict.json").exists()  # "hi" has no code: a genuine model result
    assert not (t02 / "verdict.json").exists(), "a 429 must never be scored as a model failure"
    assert "rate_limited" in (t02 / "api_error.txt").read_text(encoding="utf-8")
    assert len(sent) == 1 + 4  # 1 answer + 4 attempts at the 429
    assert f"Continue this run with --run-id {first.name}" in capsys.readouterr().out

    sent.clear()
    _fake_post(monkeypatch, [FREE_OK])
    assert runner.main(argv) == 0
    assert [p for p in free_env.iterdir() if p.is_dir()] == [run_dir]  # same run, not a new one
    assert (t02 / "verdict.json").exists() and not (t02 / "api_error.txt").exists()
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["complete"] is True and len(meta["sessions"]) == 2
    assert [s["api_calls"] for s in meta["sessions"]] == [1, 1]
    assert json.loads((free_env / ".free_quota.json").read_text(encoding="utf-8"))["requests"] == 6


def _unfinished_run(results, run_id, config, tasks, models, complete=False, **extra):
    sig = {"config": runner._rel(config), "models": models, "tasks": tasks, "trials": 1, "dry_run": False}
    (results / run_id).mkdir()
    (results / run_id / "run_meta.json").write_text(
        json.dumps({"run_id": run_id, "signature": sig, "complete": complete, **extra}), encoding="utf-8")


@pytest.mark.parametrize("tasks, models, expected", [
    (["t01_flash_sale"], [FREE_ID], "tasks added now: t02_on_call"),          # a task was added since
    (["t01_flash_sale", "t02_on_call"], ["lab/other:free"], "models added now: " + FREE_ID),  # model swapped
])
def test_a_changed_task_or_model_list_is_refused_not_started_as_a_new_run(
        tmp_path, monkeypatch, free_env, capsys, tasks, models, expected):
    config = _free_config(tmp_path)
    _unfinished_run(free_env, "old", config, tasks, models)
    sent = _fake_post(monkeypatch, [FREE_OK])
    argv = ["run", "--trials", "1", "--yes", *TWO_TASKS, "--config", str(config)]

    assert runner.main(argv) == 2
    out = capsys.readouterr().out
    assert "refusing to start a new run implicitly" in out and "old" in out and expected in out
    assert "--new" in out and "--run-id old" in out
    assert sent == [] and sorted(p.name for p in free_env.iterdir() if p.is_dir()) == ["old"]

    assert runner.main(argv + ["--new"]) == 0  # an explicit --new starts one
    assert len(sent) == 2 and len([p for p in free_env.iterdir() if p.is_dir()]) == 2


def test_with_no_unfinished_run_a_new_one_needs_new(tmp_path, monkeypatch, free_env, capsys):
    config = _free_config(tmp_path)
    _unfinished_run(free_env, "done", config, ["t01_flash_sale", "t02_on_call"], [FREE_ID], complete=True)
    sent = _fake_post(monkeypatch, [FREE_OK])
    assert runner.main(["run", "--trials", "1", "--yes", *TWO_TASKS, "--config", str(config)]) == 2
    assert "no unfinished run" in capsys.readouterr().out and sent == []


def test_an_exact_match_is_resumed_and_its_notes_survive(tmp_path, monkeypatch, free_env):
    config = _free_config(tmp_path)
    _unfinished_run(free_env, "old", config, ["t01_flash_sale", "t02_on_call"], [FREE_ID], notes="extra pilot")
    _fake_post(monkeypatch, [FREE_OK])
    assert runner.main(["run", "--trials", "1", "--yes", *TWO_TASKS, "--config", str(config)]) == 0
    assert [p.name for p in free_env.iterdir() if p.is_dir()] == ["old"]
    meta = json.loads((free_env / "old" / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["complete"] is True and meta["notes"] == "extra pilot"


def test_run_stops_cleanly_when_the_daily_quota_is_used_up(tmp_path, monkeypatch, free_env):
    (free_env / ".free_quota.json").write_text(json.dumps({"date_utc": runner.utc_today(), "requests": 49}),
                                               encoding="utf-8")
    sent = _fake_post(monkeypatch, [FREE_OK])
    argv = ["run", "--trials", "1", "--yes", *TWO_TASKS, "--config", str(_free_config(tmp_path)), "--run-id", "r"]
    assert runner.main(argv) == 1
    assert len(sent) == 1, "the 51st request of the day must never be sent"
    meta = json.loads((free_env / "r" / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["stopped_reason"].startswith("quota: 50 of 50") and meta["complete"] is False


def test_dry_run_saves_everything_and_grades_the_reference():
    run_id = f"test-dry-{uuid.uuid4().hex[:8]}"
    run_dir = runner.RESULTS / run_id
    try:
        code = runner.main(["run", "--trials", "1", "--dry-run", "--task", "t01_flash_sale",
                            "--model", runner.load_models().models[0].slug, "--run-id", run_id])
        assert code == 0
        [trial] = list(run_dir.glob("*/t01_flash_sale/trial_1"))
        names = {p.name for p in trial.iterdir()}
        assert {"prompt.txt", "request.json", "raw_response.txt", "response.json", "api.json",
                "solution.py", "verdict.json"} <= names
        verdict = json.loads((trial / "verdict.json").read_text(encoding="utf-8"))
        assert verdict["passed"] is True and verdict["api"]["cost_usd"] == 0.0
        meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
        assert meta["dry_run"] is True and meta["spent_usd"] == 0.0 and "PostgreSQL 16.15" in meta["postgres_version"]

        # Resuming the same run id skips trials that already have a verdict.
        assert runner.main(["run", "--trials", "1", "--dry-run", "--task", "t01_flash_sale",
                            "--model", runner.load_models().models[0].slug, "--run-id", run_id]) == 0
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


@pytest.mark.parametrize("failure", [
    http.client.IncompleteRead(b"x" * 1463),   # connection dropped mid-body (seen in the first pilot)
    ConnectionResetError("reset"),
    TimeoutError("timed out"),
])
def test_broken_connections_are_transport_errors(monkeypatch, failure):
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            raise failure

    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda req, timeout: Resp())
    client = OpenRouterClient("sk-test", {}, {})
    with pytest.raises(TransportError):
        client._post(b"{}")


def test_truncated_json_body_is_a_transport_error(monkeypatch):
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"choices": [{"mess'

    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda req, timeout: Resp())
    with pytest.raises(TransportError):
        OpenRouterClient("sk-test", {}, {})._post(b"{}")
