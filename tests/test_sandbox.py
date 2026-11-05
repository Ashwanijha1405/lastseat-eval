"""Loading model code: allowed imports work, anything else is rejected with a reason."""

import pytest

from lastseat.sandbox import LoadError, load_solution
from lastseat.task import all_tasks


def reason(source: str, entrypoint: str = "f") -> str:
    with pytest.raises(LoadError) as e:
        load_solution(source, entrypoint)
    return e.value.reason


@pytest.mark.parametrize(
    "line",
    [
        "import psycopg",
        "import psycopg.errors",
        "from psycopg import errors",
        "from psycopg.errors import SerializationFailure",
        "import datetime",
        "from decimal import Decimal",
        "from typing import Optional",
        "from __future__ import annotations",
    ],
)
def test_allowed_imports_load(line):
    solution = load_solution(f"{line}\ndef f(db):\n    return True\n", "f")
    assert solution.entrypoint(None) is True


@pytest.mark.parametrize(
    "line",
    ["import time", "import psycopg.sql", "from psycopg import connect", "import os, datetime", "from . import x"],
)
def test_other_imports_are_forbidden(line):
    assert reason(f"{line}\ndef f(db): pass\n") == "forbidden_import"


def test_psycopg_exposes_only_exception_classes():
    solution = load_solution(
        "import psycopg\n"
        "def f(db):\n"
        "    return psycopg.errors.SerializationFailure, psycopg.Error, hasattr(psycopg, 'connect')\n",
        "f",
    )
    failure, base, can_connect = solution.entrypoint(None)
    assert failure.sqlstate == "40001"
    assert issubclass(failure, base)
    assert not can_connect


def test_dynamic_import_is_blocked_at_runtime():
    solution = load_solution("def f(db):\n    return __import__('os')\n", "f")
    with pytest.raises(ImportError):
        solution.entrypoint(None)


def test_file_access_is_removed():
    assert reason("data = open('/etc/passwd').read()\ndef f(db): pass\n") == "exec_error"


def test_syntax_error_and_missing_function():
    assert reason("def f(db) return 1\n") == "syntax_error"
    assert reason("def g(db): pass\n") == "missing_entrypoint"


def test_migrate_is_optional():
    assert load_solution("def f(db): pass\n", "f").migrate is None
    assert load_solution("def f(db): pass\ndef migrate(db): pass\n", "f").migrate is not None


def test_every_task_solution_loads():
    for task in all_tasks():
        for path in [task.reference_path, *task.wrong_paths]:
            load_solution(path.read_text(encoding="utf-8"), task.entrypoint)
