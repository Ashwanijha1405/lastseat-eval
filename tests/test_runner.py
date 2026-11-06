"""Runner: code extraction, retries, cost guard, refusal rules, dry-run pipeline. No network."""

import json
import shutil
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


def test_free_run_caps_the_price_and_stops_on_any_reported_cost(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.delenv("LASTSEAT_MAX_COST_USD", raising=False)
    monkeypatch.setattr(runner, "fetch_catalog", lambda: {FREE_ID: {"id": FREE_ID, "pricing": ZERO}})
    sent = []

    def fake_post(self, payload):
        sent.append(json.loads(payload))
        return {**OK, "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0001}}

    monkeypatch.setattr(OpenRouterClient, "_post", fake_post)
    run_id = f"test-free-{uuid.uuid4().hex[:8]}"
    try:
        argv = ["run", "--trials", "1", "--yes", "--task", "t01_flash_sale", "--task", "t02_on_call",
                "--config", str(_free_config(tmp_path)), "--run-id", run_id]
        assert runner.main(argv) == 1
        assert len(sent) == 1, "the run must stop after the first reply that reports a cost"
        assert sent[0]["provider"] == {"max_price": {"prompt": 0, "completion": 0, "request": 0, "image": 0}}
        meta = json.loads((runner.RESULTS / run_id / "run_meta.json").read_text(encoding="utf-8"))
        assert meta["tier"] == "free" and meta["budget_limit_usd"] == 0.0
        assert "reported cost" in meta["stopped_reason"]  # stopped right after the reply, not at the next call
    finally:
        shutil.rmtree(runner.RESULTS / run_id, ignore_errors=True)


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
