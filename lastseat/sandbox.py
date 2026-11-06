"""Load model-written code and restrict what it can reach.

This guards against accidents (a stray `import time`, a second database
connection that would bypass the scheduler), not against code written to
escape. Models are not adversarial here; the grading database role is the
real security boundary.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import types
from dataclasses import dataclass
from typing import Any, Callable

import psycopg.errors

ALLOWED_MODULES = frozenset({"datetime", "decimal", "typing", "__future__"})

# `import psycopg` / `import psycopg.errors` bind this view: the exception
# classes only, no connect().
_PSYCOPG_VIEW = types.ModuleType("psycopg", "Restricted view: only the exception classes are available.")
_PSYCOPG_VIEW.errors = psycopg.errors
for _name in ("Error", "Warning", "InterfaceError", "DatabaseError", "DataError", "OperationalError",
              "IntegrityError", "InternalError", "ProgrammingError", "NotSupportedError"):
    setattr(_PSYCOPG_VIEW, _name, getattr(psycopg.errors, _name))

_REMOVED_BUILTINS = frozenset({"open", "exec", "eval", "compile", "input", "breakpoint", "exit", "quit", "help"})


@dataclass(frozen=True)
class Solution:
    functions: dict[str, Callable[..., Any]]  # every entrypoint the task names
    migrate: Callable[[Any], Any] | None


class LoadError(Exception):
    """The solution cannot be graded. `reason` is a stable machine-readable code."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason  # syntax_error | forbidden_import | exec_error | missing_entrypoint
        self.detail = detail


def load_solution(source: str, entrypoints: tuple[str, ...]) -> Solution:
    try:
        tree = ast.parse(source, filename="solution.py")
    except SyntaxError as e:
        raise LoadError("syntax_error", f"line {e.lineno}: {e.msg}") from None

    forbidden = sorted(_forbidden_imports(tree))
    if forbidden:
        raise LoadError("forbidden_import", ", ".join(forbidden))

    namespace: dict[str, Any] = {"__name__": "solution", "__builtins__": _restricted_builtins()}
    try:
        exec(compile(tree, "solution.py", "exec"), namespace)
    except Exception as e:
        raise LoadError("exec_error", f"{type(e).__name__}: {e}") from None

    missing = [name for name in entrypoints if not callable(namespace.get(name))]
    if missing:
        raise LoadError("missing_entrypoint", "no function named " + ", ".join(repr(n) for n in missing))
    migrate = namespace.get("migrate")
    return Solution({name: namespace[name] for name in entrypoints}, migrate if callable(migrate) else None)


def _forbidden_imports(tree: ast.AST) -> set[str]:
    bad: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bad.update(a.name for a in node.names if not _allowed(a.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                bad.add("." * node.level + module)
            elif module == "psycopg":
                bad.update(f"psycopg.{a.name}" for a in node.names if a.name != "errors")
            elif not _allowed(module):
                bad.add(module)
    return bad


def _allowed(module: str) -> bool:
    return module in ALLOWED_MODULES or module in ("psycopg", "psycopg.errors")


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level:
        raise ImportError("relative imports are not allowed")
    if name == "psycopg.errors" and fromlist:
        return psycopg.errors  # from psycopg.errors import X
    if name in ("psycopg", "psycopg.errors"):
        return _PSYCOPG_VIEW  # import psycopg / import psycopg.errors / from psycopg import errors
    if name in ALLOWED_MODULES:
        return importlib.import_module(name)
    raise ImportError(f"import of {name!r} is not allowed")


def _restricted_builtins() -> dict[str, Any]:
    safe = {k: v for k, v in vars(builtins).items() if k not in _REMOVED_BUILTINS}
    safe["__import__"] = _guarded_import
    return safe
