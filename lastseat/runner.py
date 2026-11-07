"""Ask models to solve the tasks via OpenRouter, save everything, grade it (SPEC §8).

    python -m lastseat.runner models [--config paid]    # live IDs + prices of the configured models
    python -m lastseat.runner models --list-free        # every zero-priced ":free" model in the catalog
    python -m lastseat.runner run --trials 1 --dry-run  # whole pipeline, mock model, $0
    python -m lastseat.runner run --trials 5 [--yes]    # real run; without --yes only prints the estimate

--config picks the model set: "free" (default, config/models.free.yaml),
"paid" (config/models.yaml), or a path. A free config is held to zero spend
in code: see check_free_config / check_free_catalog / FREE_MAX_PRICE.

The API key comes only from OPENROUTER_API_KEY and is only ever sent in the
Authorization header; it is never written to disk or printed.
"""

from __future__ import annotations

import argparse
import datetime
import http.client
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import psycopg
import yaml

from .grade import grade_in_subprocess
from .task import TASKS_DIR, Task, all_tasks, load_task

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = Path(__file__).resolve().parent / "prompts" / "contract.md"
CONFIGS = {"free": ROOT / "config" / "models.free.yaml", "paid": ROOT / "config" / "models.yaml"}
DEFAULT_CONFIG = "free"
# Sent as provider.max_price on every free-tier request: OpenRouter refuses to
# route the request to any provider that charges more than this.
FREE_MAX_PRICE = {"prompt": 0, "completion": 0, "request": 0, "image": 0}
# OpenRouter free models, account with < $10 credits ever bought: 20/min, 50/day.
FREE_LIMITS = {"min_interval_s": 4.0, "daily_requests": 50, "max_attempts": 4}
RESULTS = ROOT / "results"


def quota_file() -> Path:
    return RESULTS / ".free_quota.json"
API = "https://openrouter.ai/api/v1"

# Grader caps, recorded in run_meta.json (defaults of lastseat.grade / scheduler).
SCHEDULER_CAPS = {"max_schedules": 2000, "random_schedules": 200, "random_seed": 0,
                  "step_limit": 60, "schedule_timeout_s": 15.0}
DEFAULT_OUTPUT_TOKENS = 8000  # estimate per call when no pilot run is given
CHARS_PER_TOKEN = 4

_PY_BLOCK = re.compile(r"```python[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)


# --- configuration ----------------------------------------------------------


@dataclass(frozen=True)
class Model:
    slug: str
    id: str


@dataclass(frozen=True)
class ModelsConfig:
    path: Path
    tier: str  # "free" or "paid"
    confirmed: bool
    settings: dict[str, Any]
    models: tuple[Model, ...]
    limits: dict[str, Any] = field(default_factory=dict)  # free tier: min_interval_s, daily_requests, max_attempts

    @property
    def free(self) -> bool:
        return self.tier == "free"


def config_path(name: str | None) -> Path:
    name = name or DEFAULT_CONFIG
    if name in CONFIGS:
        return CONFIGS[name]
    p = Path(name)
    return p if p.is_absolute() else ROOT / p


def load_models(path: Path | None = None) -> ModelsConfig:
    path = path or CONFIGS[DEFAULT_CONFIG]
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    models = tuple(Model(m["slug"], m["id"]) for m in raw["models"])
    slugs = [m.slug for m in models]
    if len(set(slugs)) != len(slugs) or not all(re.fullmatch(r"[a-z0-9._-]+", s) for s in slugs):
        raise ValueError(f"{path}: model slugs must be unique and match [a-z0-9._-]+")
    tier = raw.get("tier", "paid")
    if tier not in ("free", "paid"):
        raise ValueError(f"{path}: tier must be 'free' or 'paid', not {tier!r}")
    limits = dict(raw.get("limits") or {})
    unknown = set(limits) - set(FREE_LIMITS)
    if unknown:
        raise ValueError(f"{path}: unknown limits {sorted(unknown)}; known: {sorted(FREE_LIMITS)}")
    if tier == "free":
        limits = {**FREE_LIMITS, **limits}
    config = ModelsConfig(path, tier, bool(raw.get("confirmed", False)), dict(raw.get("settings") or {}), models,
                          limits)
    if config.free:
        check_free_config(config)
    return config


def check_free_config(config: ModelsConfig) -> None:
    """Free tier, part 1 (offline): only ":free" IDs, and no way to override the price cap."""
    paid = [m.id for m in config.models if not m.id.endswith(":free")]
    if paid:
        raise ValueError(f"{config.path}: tier is free but these IDs do not end in ':free': {paid}")
    if "provider" in config.settings:
        raise ValueError(f"{config.path}: a free config may not set 'provider'; the runner pins "
                         f"provider.max_price to {FREE_MAX_PRICE}")


def is_zero_priced(entry: dict[str, Any]) -> bool:
    """Every price the catalog lists for this model (prompt, completion, request, image, ...) is 0."""
    prices = (entry.get("pricing") or {}).values()
    try:
        return bool(prices) and all(float(v) == 0 for v in prices)
    except (TypeError, ValueError):
        return False


def check_free_catalog(models: tuple[Model, ...], catalog: dict[str, dict[str, Any]]) -> list[str]:
    """Free tier, part 2 (live catalog): problems that must stop the run; empty when all is free."""
    problems = [f"{m.id}: not on OpenRouter" for m in models if m.id not in catalog]
    problems += [f"{m.id}: catalog lists a nonzero price {catalog[m.id].get('pricing')}"
                 for m in models if m.id in catalog and not is_zero_priced(catalog[m.id])]
    return problems


def build_prompt(task: Task) -> str:
    return CONTRACT.read_text(encoding="utf-8") + "\n" + task.prompt


def extract_code(text: str) -> str | None:
    """The last ```python fenced block, or None."""
    blocks = _PY_BLOCK.findall(text or "")
    return blocks[-1] if blocks else None


# --- OpenRouter -------------------------------------------------------------


class TransportError(Exception):
    """Retryable: rate limit, server error, network failure. Never the model's fault."""

    def __init__(self, message: str, *, status: int | None = None, retry_after_s: float | None = None,
                 daily_exhausted: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after_s = retry_after_s
        self.daily_exhausted = daily_exhausted  # retrying cannot help before the reset


class ApiError(Exception):
    """Not retryable: the request itself was rejected."""


class QuotaExhausted(Exception):
    """The local daily counter says no free-model requests are left today."""


def _sleep(seconds: float) -> None:  # module-level so tests can replace it
    time.sleep(seconds)


def utc_today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


class RateLimiter:
    """At most one request start every `min_interval_s` seconds."""

    def __init__(self, min_interval_s: float, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = _sleep) -> None:
        self.min_interval_s = min_interval_s
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        if self._last is not None:
            gap = self._last + self.min_interval_s - self._clock()
            if gap > 0:
                self._sleep(gap)
        self._last = self._clock()


class DailyQuota:
    """Requests sent to free models in the current UTC day, persisted across runs.

    Every HTTP attempt is counted before it is sent (retries too): OpenRouter
    does not document whether failed free-model requests count, so we assume
    they do."""

    def __init__(self, path: Path, limit: int, *, today: Callable[[], str] = utc_today) -> None:
        self.path = path
        self.limit = limit
        self._today = today

    def used(self) -> int:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 0
        return int(data.get("requests", 0)) if data.get("date_utc") == self._today() else 0

    def remaining(self) -> int:
        return max(0, self.limit - self.used())

    def _write(self, used: int) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"date_utc": self._today(), "requests": used, "limit": self.limit}),
                       encoding="utf-8")
        tmp.replace(self.path)

    def take(self) -> None:
        used = self.used()
        if used >= self.limit:
            raise QuotaExhausted(f"{used} of {self.limit} free-model requests used today ({self._today()} UTC); "
                                 "the counter resets at 00:00 UTC")
        self._write(used + 1)

    def sync(self, server: dict[str, Any] | None) -> None:
        """Adopt OpenRouter's own count (GET /key) when it is higher or its limit lower."""
        if not server:
            return
        if server.get("limit") is not None:
            self.limit = min(self.limit, int(server["limit"]))
        if int(server.get("used") or 0) > self.used():
            self._write(int(server["used"]))


class FreeGate:
    """Called before every HTTP attempt to a free model: count it, then pace it."""

    def __init__(self, quota: DailyQuota, limiter: RateLimiter) -> None:
        self.quota = quota
        self.limiter = limiter

    def acquire(self) -> None:
        self.quota.take()
        self.limiter.wait()


@dataclass
class Reply:
    content: str
    raw: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    seconds: float
    attempts: int


def fetch_catalog() -> dict[str, dict[str, Any]]:
    with urllib.request.urlopen(f"{API}/models", timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))["data"]
    return {m["id"]: m for m in data}


def price_per_token(entry: dict[str, Any]) -> tuple[float, float]:
    p = entry.get("pricing", {})
    return float(p.get("prompt", 0)), float(p.get("completion", 0))


def fetch_key_status(api_key: str) -> dict[str, Any] | None:
    """OpenRouter's free-model counter for this key ({used, limit, remaining}), or None.
    Only that sub-object is returned: the rest of /key (label etc.) is never stored."""
    req = urllib.request.Request(f"{API}/key", headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8")).get("data") or {}
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
        return None
    free = data.get("free_model_daily_requests")
    return {k: free.get(k) for k in ("used", "limit", "remaining")} if isinstance(free, dict) else None


def _rate_limit_error(code: int, headers: Any, detail: str) -> TransportError:
    retry_after = None
    try:
        retry_after = float(headers.get("Retry-After")) if headers.get("Retry-After") else None
    except (TypeError, ValueError):
        pass
    daily = False
    try:  # free-model 429s carry X-RateLimit-Reset in ms since the epoch
        reset_ms = float(headers.get("X-RateLimit-Reset"))
        daily = headers.get("X-RateLimit-Remaining") == "0" and reset_ms / 1000 - time.time() > 120
    except (TypeError, ValueError):
        pass
    reset = headers.get("X-RateLimit-Reset")
    return TransportError(f"HTTP {code}" + (f" (X-RateLimit-Reset={reset})" if reset else "") + f": {detail[:300]}",
                          status=code, retry_after_s=retry_after, daily_exhausted=daily)


class OpenRouterClient:
    def __init__(self, api_key: str, settings: dict[str, Any], prices: dict[str, tuple[float, float]],
                 *, max_attempts: int = 6, sleep: Callable[[float], None] = _sleep,
                 gate: FreeGate | None = None) -> None:
        self._key = api_key
        self.settings = settings
        self.prices = prices
        self.max_attempts = max_attempts
        self._sleep = sleep
        self.gate = gate

    def body(self, model: Model, prompt: str) -> dict[str, Any]:
        return {"model": model.id, "messages": [{"role": "user", "content": prompt}],
                "usage": {"include": True}, **self.settings}

    def complete(self, model: Model, prompt: str) -> Reply:
        payload = json.dumps(self.body(model, prompt)).encode("utf-8")
        started = time.monotonic()
        for attempt in range(1, self.max_attempts + 1):
            if self.gate:
                self.gate.acquire()  # may raise QuotaExhausted
            try:
                raw = self._post(payload)
                return self._reply(model, raw, time.monotonic() - started, attempt)
            except TransportError as e:
                if e.daily_exhausted or attempt == self.max_attempts:
                    raise
                wait = e.retry_after_s if e.retry_after_s is not None else min(60.0, 2.0 ** (attempt + 1))
                wait = min(120.0, wait) + random.uniform(0, 1)
                print(f"    transport error ({e}); retry {attempt}/{self.max_attempts - 1} in {wait:.0f}s",
                      flush=True)
                self._sleep(wait)
        raise AssertionError("unreachable")

    def _post(self, payload: bytes) -> dict[str, Any]:
        req = urllib.request.Request(
            f"{API}/chat/completions", data=payload, method="POST",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
                     "X-Title": "LastSeat eval"},
        )
        try:
            with urllib.request.urlopen(req, timeout=900) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:1000]
            if e.code == 429:
                raise _rate_limit_error(e.code, e.headers, detail) from None
            if e.code >= 500:
                raise TransportError(f"HTTP {e.code}: {detail[:300]}", status=e.code) from None
            raise ApiError(f"HTTP {e.code}: {detail}") from None
        except (OSError, http.client.HTTPException, ValueError) as e:
            # URLError, timeouts and resets are OSErrors; a connection dropped mid-body
            # raises IncompleteRead (HTTPException); a truncated body fails to parse (ValueError).
            raise TransportError(f"{type(e).__name__}: {str(e)[:200]}") from None
        error = raw.get("error")
        if error:
            code = error.get("code") if isinstance(error, dict) else None
            if isinstance(code, int) and (code == 429 or code >= 500):
                raise TransportError(f"error {code}: {json.dumps(error)[:300]}", status=code)
            raise ApiError(json.dumps(error)[:1000])
        return raw

    def _reply(self, model: Model, raw: dict[str, Any], seconds: float, attempts: int) -> Reply:
        choices = raw.get("choices") or [{}]
        content = (choices[0].get("message") or {}).get("content") or ""
        usage = raw.get("usage") or {}
        pt, ct = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
        cost = usage.get("cost")
        if cost is None:  # fall back to list prices
            pin, pout = self.prices.get(model.id, (0.0, 0.0))
            cost = pt * pin + ct * pout
        return Reply(content, raw, pt, ct, float(cost), round(seconds, 2), attempts)


class MockClient:
    """--dry-run: answers every task with its reference solution, at zero cost."""

    settings: dict[str, Any] = {"mock": "returns reference.py"}

    def __init__(self, tasks: dict[str, Task]) -> None:
        self._by_prompt = {build_prompt(t): t for t in tasks.values()}

    def body(self, model: Model, prompt: str) -> dict[str, Any]:
        return {"model": model.id, "mock": True}

    def complete(self, model: Model, prompt: str) -> Reply:
        task = self._by_prompt[prompt]
        code = task.reference_path.read_text(encoding="utf-8")
        content = f"Here is my solution.\n\n```python\n{code}```\n"
        raw = {"mock": True, "model": model.id, "choices": [{"message": {"content": content}}],
               "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}}
        return Reply(content, raw, 0, 0, 0.0, 0.0, 1)


# --- cost -------------------------------------------------------------------


@dataclass
class Budget:
    max_usd: float
    spent_usd: float = 0.0
    stopped_reason: str | None = None

    def allows(self, worst_case_usd: float) -> bool:
        return self.spent_usd + worst_case_usd <= self.max_usd


def estimate(tasks: list[Task], models: tuple[Model, ...], trials: int, prices: dict[str, tuple[float, float]],
             max_tokens: int, typical_output: dict[str, float]) -> list[dict[str, Any]]:
    rows = []
    for m in models:
        pin, pout = prices.get(m.id, (0.0, 0.0))
        in_tok = sum(len(build_prompt(t)) / CHARS_PER_TOKEN for t in tasks) * trials
        calls = len(tasks) * trials
        out_typ = typical_output.get(m.slug, DEFAULT_OUTPUT_TOKENS) * calls
        rows.append({"model": m.slug, "calls": calls,
                     "typical_usd": in_tok * pin + out_typ * pout,
                     "worst_usd": in_tok * pin + max_tokens * calls * pout})
    return rows


def typical_output_from(run_dir: Path) -> dict[str, float]:
    """Mean completion tokens per model slug in an earlier (pilot) run."""
    sums: dict[str, list[int]] = {}
    for v in run_dir.glob("*/*/trial_*/verdict.json"):
        api = json.loads(v.read_text(encoding="utf-8")).get("api") or {}
        if api.get("completion_tokens"):
            sums.setdefault(v.parents[2].name, []).append(api["completion_tokens"])
    return {slug: sum(xs) / len(xs) for slug, xs in sums.items()}


# --- run --------------------------------------------------------------------


def git_commit() -> str:
    head = ROOT / ".git" / "HEAD"
    try:
        ref = head.read_text().strip()
        if not ref.startswith("ref: "):
            return ref
        name = ref[5:]
        loose = ROOT / ".git" / name
        if loose.exists():
            return loose.read_text().strip()
        for line in (ROOT / ".git" / "packed-refs").read_text().splitlines():
            if line.endswith(" " + name):
                return line.split()[0]
    except OSError:
        pass
    return "unknown"


def postgres_version() -> str:
    try:
        with psycopg.connect(autocommit=True) as c:
            return c.execute("SELECT version()").fetchone()[0]
    except psycopg.Error as e:
        return f"unavailable: {e}"


@dataclass
class Job:
    model: Model
    task: Task
    trial: int
    out: Path


@dataclass
class RunState:
    """run_meta.json across sessions: totals at the top, one entry per invocation in `sessions`."""
    run_dir: Path
    meta: dict[str, Any]
    budget: Budget
    calls: int = 0
    failures: list[str] = field(default_factory=list)
    calls_before: int = 0

    def save_meta(self) -> None:
        session = self.meta["sessions"][-1]
        session.update(api_calls=self.calls - self.calls_before, stopped_reason=self.budget.stopped_reason,
                       api_failures=self.failures)
        self.meta.update(spent_usd=round(self.budget.spent_usd, 6), api_calls=self.calls,
                         stopped_reason=self.budget.stopped_reason)
        (self.run_dir / "run_meta.json").write_text(json.dumps(self.meta, indent=2), encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=repr), encoding="utf-8")


def ask(client, job: Job, state: RunState, worst_case_usd: float) -> Path | None:
    """Call the model for one trial and save its outputs. Returns the solution
    path, or None when no gradable code exists (verdict already written)."""
    job.out.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(job.task)
    (job.out / "prompt.txt").write_text(prompt, encoding="utf-8")
    _write_json(job.out / "request.json", client.body(job.model, "<prompt.txt>"))
    if not state.budget.allows(worst_case_usd):
        state.budget.stopped_reason = (f"budget: spent ${state.budget.spent_usd:.4f}; next call could cost up to "
                                       f"${worst_case_usd:.4f}; limit ${state.budget.max_usd:.2f}")
        return None
    # None of these is the model's fault, so no verdict is written: the cell
    # stays missing and re-running the same command asks it again.
    cell = f"{job.model.slug}/{job.task.id}/trial_{job.trial}"
    try:
        reply = client.complete(job.model, prompt)
    except QuotaExhausted as e:
        state.budget.stopped_reason = f"quota: {e}"
        return None
    except (TransportError, ApiError) as e:
        kind = ("rate_limited" if isinstance(e, TransportError) and e.status == 429
                else "transport" if isinstance(e, TransportError) else "api_error")
        state.failures.append(f"{cell}: {kind}: {e}")
        (job.out / "api_error.txt").write_text(f"{kind}\n{e}\n", encoding="utf-8")
        state.budget.stopped_reason = f"{kind} at {cell}: {e}"
        return None
    state.calls += 1
    state.budget.spent_usd += reply.cost_usd
    if state.budget.spent_usd > state.budget.max_usd:  # a free run has max_usd 0: any reported cost stops it
        state.budget.stopped_reason = (f"budget: {job.model.id} reported cost ${reply.cost_usd:.6f}; spent "
                                       f"${state.budget.spent_usd:.6f} > limit ${state.budget.max_usd:.2f}")
    (job.out / "raw_response.txt").write_text(reply.content, encoding="utf-8")
    _write_json(job.out / "response.json", reply.raw)
    (job.out / "api_error.txt").unlink(missing_ok=True)  # left by an earlier, interrupted attempt
    finish = ((reply.raw.get("choices") or [{}])[0] or {}).get("finish_reason")
    api = {"model_id": job.model.id, "served_model": reply.raw.get("model"), "provider": reply.raw.get("provider"),
           "finish_reason": finish,
           "prompt_tokens": reply.prompt_tokens, "completion_tokens": reply.completion_tokens,
           "cost_usd": reply.cost_usd, "seconds": reply.seconds, "attempts": reply.attempts}
    _write_json(job.out / "api.json", api)
    code = extract_code(reply.content)
    if code is None:
        _write_json(job.out / "verdict.json", {"task_id": job.task.id, "status": "load_error",
                                               "load_error": "no_code", "failure_category": "load",
                                               "passed": False,
                                               "scores": {"safety": 0.0, "solo": 0.0, "liveness": 0.0, "total": 0.0},
                                               "api": api})
        return None
    solution = job.out / "solution.py"
    solution.write_text(code, encoding="utf-8")
    return solution


def finish_grade(job: Job, solution: Path) -> dict[str, Any]:
    verdict = grade_in_subprocess(job.task.directory, solution, job.out)
    api_file = job.out / "api.json"
    verdict["api"] = json.loads(api_file.read_text(encoding="utf-8")) if api_file.exists() else None
    _write_json(job.out / "verdict.json", verdict)
    return verdict


def run(args: argparse.Namespace) -> int:
    tasks = [load_task(TASKS_DIR / t) for t in args.task] if args.task else all_tasks()
    config = load_models(config_path(args.config))
    models = tuple(m for m in config.models if not args.model or m.slug in args.model)
    if not models:
        print("no models selected")
        return 2

    if args.dry_run:
        client = MockClient({t.id: t for t in tasks})
        prices: dict[str, tuple[float, float]] = {}
        max_usd = 0.0
    else:
        if not config.confirmed:
            print(f"refusing to call models: {config.path} has confirmed: false.\n"
                  "Run `make models` (or .\\run.ps1 models), check every ID and price, then set confirmed: true.")
            return 2
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        limit = os.environ.get("LASTSEAT_MAX_COST_USD", "").strip()
        if not key:
            print("set OPENROUTER_API_KEY in .env")
            return 2
        if config.free:
            if limit and float(limit) != 0:
                print(f"refusing a free run: LASTSEAT_MAX_COST_USD={limit}. A free run is capped at $0; "
                      "set it to 0 (or unset it), or use --config paid for a paid run.")
                return 2
            max_usd = 0.0
        else:
            if not limit or float(limit) <= 0:
                print("a paid run needs LASTSEAT_MAX_COST_USD > 0 in .env")
                return 2
            max_usd = float(limit)
        catalog = fetch_catalog()
        problems = (check_free_catalog(models, catalog) if config.free
                    else [f"{m.id}: not on OpenRouter" for m in models if m.id not in catalog])
        if problems:
            print("refusing to start:\n  " + "\n  ".join(problems))
            return 2
        prices = {m.id: price_per_token(catalog[m.id]) for m in models}
        settings = dict(config.settings)
        if config.free:
            settings["provider"] = {"max_price": dict(FREE_MAX_PRICE)}
        client = OpenRouterClient(key, settings, prices, sleep=_sleep)

    max_tokens = int(config.settings.get("max_tokens", DEFAULT_OUTPUT_TOKENS))
    typical = typical_output_from(RESULTS / args.estimate_from) if args.estimate_from else {}
    rows = estimate(tasks, models, args.trials, prices, max_tokens, typical)
    basis = f"pilot run {args.estimate_from}" if typical else f"assumed {DEFAULT_OUTPUT_TOKENS} output tokens/call"
    print(f"{len(models)} model(s) x {len(tasks)} task(s) x {args.trials} trial(s); estimate ({basis}):")
    for r in rows:
        print(f"  {r['model']:24} {r['calls']:4} calls  typical ${r['typical_usd']:8.2f}  worst ${r['worst_usd']:8.2f}")
    print(f"  {'TOTAL':24} {sum(r['calls'] for r in rows):4} calls  typical ${sum(r['typical_usd'] for r in rows):8.2f}"
          f"  worst ${sum(r['worst_usd'] for r in rows):8.2f}   budget limit ${max_usd:.2f}")

    signature = {"config": _rel(config.path), "models": [m.id for m in models], "tasks": [t.id for t in tasks],
                 "trials": args.trials, "dry_run": args.dry_run}
    run_id = args.run_id
    if not run_id and not args.new and not args.dry_run:  # a dry run makes no model calls: always fresh
        run_id, refusal = find_resumable(signature)
        if refusal:
            print(refusal)
            return 2
    resuming = run_id is not None and (RESULTS / run_id / "run_meta.json").exists()
    run_id = run_id or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + (
        "-dry" if args.dry_run else "")
    run_dir = RESULTS / run_id
    jobs = [Job(m, t, n, run_dir / m.slug / t.id / f"trial_{n}")
            for n in range(1, args.trials + 1) for m in models for t in tasks]
    todo = [j for j in jobs if not (j.out / "verdict.json").exists()]
    print(f"run {run_id}: {'resuming, ' if resuming else 'new, '}{len(jobs) - len(todo)} of {len(jobs)} cells done, "
          f"{len(todo)} to ask" + ("" if args.run_id or args.new else "  (--new starts a fresh run)"))

    gate = None
    if config.free and not args.dry_run:
        quota = DailyQuota(quota_file(), int(config.limits["daily_requests"]))
        server = fetch_key_status(key)
        quota.sync(server)
        print(f"free-model requests today ({utc_today()} UTC): {quota.used()} used of {quota.limit}, "
              f"{quota.remaining()} left" + (f"  [OpenRouter reports {server}]" if server
                                            else "  [OpenRouter /key unavailable; local count only]"))
        if quota.remaining() < len(todo):
            print(f"  note: {len(todo)} cells to ask but only {quota.remaining()} requests left today; the run "
                  f"will stop cleanly when they are used up. Continue after 00:00 UTC with --run-id {run_id}.")
        gate = FreeGate(quota, RateLimiter(float(config.limits["min_interval_s"]), sleep=_sleep))
        client.gate = gate
        client.max_attempts = int(config.limits["max_attempts"])
    if not args.dry_run and not args.yes:
        print("estimate only; re-run with --yes (make ... YES=1, .\\run.ps1 ... -Yes) to start")
        return 0
    if not todo:
        print("nothing to do")
        return 0

    run_dir.mkdir(parents=True, exist_ok=True)
    meta_file = run_dir / "run_meta.json"
    prior = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    state = RunState(run_dir, {
        "run_id": run_id, "signature": signature,
        "started_utc": prior.get("started_utc", now),
        "git_commit": git_commit(), "dry_run": args.dry_run, "trials": args.trials,
        "config": _rel(config.path), "tier": config.tier, "limits": config.limits,
        "tasks": [t.id for t in tasks], "models": [{"slug": m.slug, "id": m.id} for m in models],
        "settings_sent": client.settings, "list_prices_usd_per_token": prices,
        "postgres_version": postgres_version(), "scheduler_caps": SCHEDULER_CAPS,
        "grading_jobs": args.jobs, "budget_limit_usd": max_usd, "complete": False,
        "sessions": prior.get("sessions", []) + [{"started_utc": now, "git_commit": git_commit()}],
        **({"notes": prior["notes"]} if "notes" in prior else {}),  # human notes survive a resume
    }, Budget(max_usd, spent_usd=float(prior.get("spent_usd", 0.0))),
        calls=int(prior.get("api_calls", 0)), calls_before=int(prior.get("api_calls", 0)))
    state.save_meta()

    pin_pout = {m.id: prices.get(m.id, (0.0, 0.0)) for m in models}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = []
        for job in todo:
            pin, pout = pin_pout[job.model.id]
            worst = len(build_prompt(job.task)) / CHARS_PER_TOKEN * pin + max_tokens * pout
            solution = ask(client, job, state, worst)
            state.save_meta()
            if solution:  # an answer that was already received is graded even if the run now stops
                pending.append((job, pool.submit(finish_grade, job, solution)))
            if state.budget.stopped_reason:
                print(f"STOPPED: {state.budget.stopped_reason}")
                break
            left = f", {gate.quota.remaining()} free requests left today" if gate else ""
            print(f"  {job.model.slug}/{job.task.id}/trial_{job.trial}: "
                  f"{'grading' if solution else 'no gradable code'} (spent ${state.budget.spent_usd:.4f}{left})",
                  flush=True)
        for job, fut in pending:
            v = fut.result()
            print(f"  graded {job.model.slug}/{job.task.id}/trial_{job.trial}: "
                  f"status={v.get('status')} passed={v.get('passed')} total={v.get('scores', {}).get('total')}")

    missing = sum(1 for j in jobs if not (j.out / "verdict.json").exists())
    state.meta["complete"] = missing == 0
    state.meta["sessions"][-1]["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")
    state.save_meta()
    print(f"run {run_id}: {state.calls - state.calls_before} API call(s) this session, "
          f"spent ${state.budget.spent_usd:.4f} -> {run_dir}")
    if gate:
        print(f"free-model requests left today: {gate.quota.remaining()} of {gate.quota.limit}")
    if missing:
        print(f"{missing} cell(s) still missing. Continue this run with --run-id {run_id} "
              f"(.\\run.ps1 ... -Run {run_id}, make ... RUN={run_id}).")
    return 1 if state.budget.stopped_reason else 0


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def _unfinished_runs(config: str, dry_run: bool) -> list[tuple[str, dict[str, Any]]]:
    """Unfinished runs of this config, newest first, as (run_id, signature)."""
    out = []
    for meta_file in sorted(RESULTS.glob("*/run_meta.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sig = meta.get("signature") or {}
        if not meta.get("complete") and sig.get("config") == config and bool(sig.get("dry_run")) == dry_run:
            out.append((meta_file.parent.name, sig))
    return out


def _differences(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    out = []
    for key in ("tasks", "models"):
        added = [x for x in new.get(key, []) if x not in old.get(key, [])]
        removed = [x for x in old.get(key, []) if x not in new.get(key, [])]
        if added:
            out.append(f"{key} added now: {', '.join(added)}")
        if removed:
            out.append(f"{key} only in that run: {', '.join(removed)}")
    if old.get("trials") != new.get("trials"):
        out.append(f"trials {old.get('trials')} there, {new.get('trials')} now")
    return out


def find_resumable(signature: dict[str, Any]) -> tuple[str | None, str | None]:
    """(run to resume, None), or (None, why this command needs an explicit --new or --run-id).

    Only an unfinished run with exactly this config, models, tasks and trials is
    resumed. Anything else is refused rather than silently starting a new run:
    a new run asks every cell again, which spends requests.
    """
    runs = _unfinished_runs(signature["config"], bool(signature.get("dry_run")))
    for run_id, sig in runs:
        if sig == signature:
            return run_id, None
    if runs:
        run_id, sig = runs[0]
        return None, (f"refusing to start a new run implicitly: the newest unfinished run of this config, {run_id}, "
                      "does not match this command:\n  " + "\n  ".join(_differences(sig, signature) or ["(other)"])
                      + f"\nPass --run-id {run_id} to continue that run with this command's tasks and models "
                      "(.\\run.ps1 ... -Run <id>, make ... RUN=<id>), or --new (-New, NEW=1) to start a fresh one.")
    return None, ("refusing to start a new run implicitly: there is no unfinished run of this config to resume.\n"
                  "Pass --new (.\\run.ps1 ... -New, make ... NEW=1) to start one.")


def quota_cmd(args: argparse.Namespace) -> int:
    config = load_models(config_path(args.config))
    if not config.free:
        print(f"{config.path.name} is not a free config; no request quota applies")
        return 0
    quota = DailyQuota(quota_file(), int(config.limits["daily_requests"]))
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    server = fetch_key_status(key) if key else None
    print(f"local counter ({quota_file().name}): {quota.used()} used of {quota.limit} today ({utc_today()} UTC), "
          f"{quota.remaining()} left")
    print(f"OpenRouter /key free_model_daily_requests: {server if server else 'unavailable'}")
    return 0


def list_free(catalog: dict[str, dict[str, Any]]) -> int:
    free = sorted((m for i, m in catalog.items() if i.endswith(":free") and is_zero_priced(m)),
                  key=lambda m: -m.get("created", 0))
    print(f"{len(free)} zero-priced ':free' models of {len(catalog)} (newest first)")
    print(f"{'OpenRouter id':52} {'context':>9} {'max out':>8}  created     reasoning")
    for m in free:
        created = datetime.date.fromtimestamp(m.get("created", 0)).isoformat()
        max_out = (m.get("top_provider") or {}).get("max_completion_tokens") or 0
        reasoning = "reasoning" in (m.get("supported_parameters") or [])
        print(f"{m['id']:52} {m.get('context_length', 0):9} {max_out:8}  {created}  {reasoning}")
    return 0


def models_cmd(args: argparse.Namespace) -> int:
    catalog = fetch_catalog()
    if args.list_free:
        return list_free(catalog)
    config = load_models(config_path(args.config))
    print(f"config: {config.path.name}   tier: {config.tier}   confirmed: {config.confirmed}")
    print(f"settings sent to every model: {json.dumps(config.settings)}"
          + (f" + provider.max_price={json.dumps(FREE_MAX_PRICE)}" if config.free else ""))
    if config.free:
        for problem in check_free_catalog(config.models, catalog):
            print(f"  FREE-TIER CHECK FAILS: {problem}")
    print(f"{'slug':22} {'OpenRouter id':38} {'$/M in':>8} {'$/M out':>8} {'context':>9}  supports")
    ok = True
    for m in config.models:
        entry = catalog.get(m.id)
        if entry is None:
            ok = False
            print(f"{m.slug:22} {m.id:38}  NOT FOUND on OpenRouter")
            continue
        pin, pout = price_per_token(entry)
        sp = set(entry.get("supported_parameters") or [])
        flags = ",".join(p for p in ("reasoning", "max_tokens", "temperature") if p in sp)
        print(f"{m.slug:22} {m.id:38} {pin * 1e6:8.3f} {pout * 1e6:8.3f} {entry.get('context_length', 0):9}  {flags}")
        for k in config.settings:
            if k not in sp:
                print(f"{'':22} warning: {k!r} not in this model's supported_parameters")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="LastSeat model runner")
    sub = p.add_subparsers(dest="cmd", required=True)
    config_help = "model set: free (default, config/models.free.yaml), paid (config/models.yaml), or a path"
    mo = sub.add_parser("models", help="show live IDs and prices of the configured models")
    mo.add_argument("--config", default=DEFAULT_CONFIG, help=config_help)
    mo.add_argument("--list-free", action="store_true", help="list every zero-priced ':free' model instead")
    r = sub.add_parser("run", help="ask models, save outputs, grade")
    r.add_argument("--config", default=DEFAULT_CONFIG, help=config_help)
    r.add_argument("--trials", type=int, default=5)
    r.add_argument("--task", action="append", help="task id (repeatable); default all")
    r.add_argument("--model", action="append", help="model slug (repeatable); default all")
    r.add_argument("--dry-run", action="store_true", help="mock model returning the reference; $0")
    r.add_argument("--yes", action="store_true", help="start the run after printing the estimate")
    r.add_argument("--run-id", help="results/<run-id>, created or continued; default: resume the unfinished run with "
                                    "exactly this config, models, tasks and trials, else refuse")
    r.add_argument("--new", action="store_true", help="start a new run (never done implicitly)")
    r.add_argument("--estimate-from", help="earlier run id whose token counts drive the estimate")
    r.add_argument("--jobs", type=int, default=1, help="solutions graded in parallel")
    q = sub.add_parser("quota", help="free-model requests used and left today")
    q.add_argument("--config", default=DEFAULT_CONFIG, help=config_help)
    args = p.parse_args(argv)
    return {"models": models_cmd, "quota": quota_cmd, "run": run}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
