"""latent_api_error: psycopg.errors names the pinned psycopg does not define."""

import json

import pytest

from lastseat.grade import grade
from lastseat.static_check import latent_api_errors
from lastseat.summary import summarize
from lastseat.task import TASKS_DIR, load_task

T01 = load_task(TASKS_DIR / "t01_flash_sale")


def names(source: str) -> list[str]:
    return [w["name"] for w in latent_api_errors(source)]


@pytest.mark.parametrize("source", [
    "import psycopg\nE = (psycopg.errors.TransactionRollbackError,)",
    "import psycopg.errors\nE = (psycopg.errors.TransactionRollbackError,)",
    "import psycopg.errors as pe\nE = (pe.TransactionRollbackError,)",
    "from psycopg import errors\ntry:\n    pass\nexcept errors.TransactionRollbackError:\n    pass",
    "from psycopg import errors as E\ndef f():\n    raise E.TransactionRollbackError",
    "from psycopg.errors import TransactionRollbackError",
    "def f():\n    import psycopg\n    return psycopg.errors.TransactionRollbackError",
])
def test_every_import_form_is_followed(source):
    assert names(source) == ["psycopg.errors.TransactionRollbackError"]


def test_names_psycopg_has_are_fine():
    src = ("import psycopg\nfrom psycopg import errors\n"
           "E = (psycopg.errors.SerializationFailure, errors.DeadlockDetected, errors.TransactionRollback,"
           " psycopg.errors.LockNotAvailable, psycopg.OperationalError)")
    assert latent_api_errors(src) == []


def test_unrelated_errors_names_are_ignored():
    # `errors` here is not psycopg's module, and nothing names psycopg at all.
    assert latent_api_errors("import errors\nx = errors.TransactionRollbackError") == []
    assert latent_api_errors("class errors: pass\nx = errors.Whatever") == []


def test_lines_are_collected_and_unparseable_code_gives_no_warning():
    src = "from psycopg import errors\na = errors.Nope\nb = 1\nc = errors.Nope\nd = errors.AlsoNope"
    ws = latent_api_errors(src)
    assert [(w["name"], w["lines"]) for w in ws] == [("psycopg.errors.AlsoNope", [5]), ("psycopg.errors.Nope", [2, 4])]
    assert all(w["kind"] == "latent_api_error" and "pinned psycopg 3." in w["detail"] for w in ws)
    assert latent_api_errors("def f(:\n") == []


# The reference, plus a retry clause naming psycopg2's class. No exception ever
# reaches the clause, so Python never looks the name up: the solution passes.
LATENT = T01.reference_path.read_text(encoding="utf-8").replace(
    "def purchase(db, product_id: int, qty: int) -> bool:\n",
    "from psycopg import errors\n\n\ndef purchase(db, product_id: int, qty: int) -> bool:\n"
    "    try:\n        return _purchase(db, product_id, qty)\n"
    "    except errors.TransactionRollbackError:\n        return False\n\n\n"
    "def _purchase(db, product_id: int, qty: int) -> bool:\n")
BAD_LINE = next(n for n, line in enumerate(LATENT.splitlines(), 1) if "TransactionRollbackError" in line)


def test_a_latent_bad_name_warns_but_never_changes_the_score(tmp_path):
    v = grade(T01, LATENT)
    assert v.passed and v.scores["total"] == 1.0, "the warning must not change the verdict"
    assert [(w["kind"], w["name"]) for w in v.warnings] == [("latent_api_error", "psycopg.errors.TransactionRollbackError")]
    assert json.loads(v.to_json())["warnings"][0]["lines"] == [BAD_LINE]
    assert grade(T01, T01.reference_path.read_text(encoding="utf-8")).warnings == []


def test_summary_shows_the_warning(tmp_path):
    run = tmp_path / "r"
    trial = run / "m" / "t01_flash_sale" / "trial_1"
    trial.mkdir(parents=True)
    (run / "run_meta.json").write_text(json.dumps({
        "run_id": "r", "tier": "test", "trials": 1, "tasks": ["t01_flash_sale"],
        "models": [{"slug": "m", "source": "openrouter"}]}), encoding="utf-8")
    (trial / "verdict.json").write_text(grade(T01, LATENT).to_json(), encoding="utf-8")
    text = summarize(run)
    assert "PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) ⚠ latent_api_error" in text
    assert "## Warnings (do not change the score)" in text
    assert f"`psycopg.errors.TransactionRollbackError` at line(s) {BAD_LINE}:" in text
    assert "passed anyway" in text
