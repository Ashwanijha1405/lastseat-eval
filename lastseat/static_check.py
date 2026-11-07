"""Static warnings about solution code; they never change a score.

latent_api_error: a reference to psycopg.errors.<Name> where the pinned psycopg
has no such name. Python looks such a name up only when the line runs; inside an
`except (...)` clause that is only when an exception reaches it, so a solution
can pass every schedule and still crash in production (e.g. psycopg2's
`TransactionRollbackError`; psycopg 3 calls it `TransactionRollback`).
"""
from __future__ import annotations

import ast

import psycopg
import psycopg.errors

LATENT_API_ERROR = "latent_api_error"


def latent_api_errors(source: str) -> list[dict]:
    """One warning per missing psycopg.errors name, with every line that uses it."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # the loader reports it as a load error
    packages, modules = set(), set()  # names bound to psycopg / to psycopg.errors
    lines: dict[str, list[int]] = {}

    def check(name: str, line: int) -> None:
        if not hasattr(psycopg.errors, name):
            lines.setdefault(name, []).append(line)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "psycopg.errors" and a.asname:
                    modules.add(a.asname)
                elif a.name.split(".")[0] == "psycopg" and not a.asname:
                    packages.add("psycopg")
                elif a.name == "psycopg":
                    packages.add(a.asname)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            for a in node.names:
                if node.module == "psycopg" and a.name == "errors":
                    modules.add(a.asname or "errors")
                elif node.module == "psycopg.errors" and a.name != "*":
                    check(a.name, node.lineno)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        base = node.value
        if isinstance(base, ast.Name) and base.id in modules:
            check(node.attr, node.lineno)
        elif (isinstance(base, ast.Attribute) and base.attr == "errors"
              and isinstance(base.value, ast.Name) and base.value.id in packages):
            check(node.attr, node.lineno)

    return [{"kind": LATENT_API_ERROR, "name": f"psycopg.errors.{name}", "lines": sorted(set(ls)),
             "detail": f"not defined in the pinned psycopg {psycopg.__version__}"}
            for name, ls in sorted(lines.items())]
