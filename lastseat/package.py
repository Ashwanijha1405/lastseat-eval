"""Check a submission zip before it leaves the machine: python -m lastseat.package lastseat-eval.zip

The zip itself is built by `git archive` from HEAD (make zip / .\\run.ps1 zip), so it holds
exactly the committed files. This module only inspects the result and exits 1 on any problem:
size >= 50 MB, no README.md at the root, a .env file, caches, videos, text that looks like an
API key, or the actual value of any *KEY* / *TOKEN* / *SECRET* environment variable (compose
loads .env into the container, so the real keys are checked without ever being printed).
"""

from __future__ import annotations

import os
import re
import sys
import zipfile
from pathlib import PurePosixPath

LIMIT_BYTES = 50_000_000
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".wmv", ".flv"}
CACHE_PARTS = {"__pycache__", ".pytest_cache", ".venv", "venv", ".mypy_cache"}
KEY_PATTERNS = {
    "OpenRouter key": re.compile(rb"sk-or-v1-[0-9a-f]{32,}"),
    "Anthropic key": re.compile(rb"sk-ant-[A-Za-z0-9_-]{20,}"),
    "OpenAI-style key": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9]{32,}"),
    "Google API key": re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
    "GitHub token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{36}"),
    "private key": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "key assignment": re.compile(rb"[A-Z_]*(?:API_KEY|TOKEN|SECRET)\s*[=:]\s*[\"']?[A-Za-z0-9_\-]{20,}"),
}
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET", re.IGNORECASE)


def secret_values(env) -> dict[str, bytes]:
    """Environment values that are secrets: name mentions KEY/TOKEN/SECRET and the value is long."""
    return {k: v.encode() for k, v in env.items() if SECRET_NAME.search(k) and len(v.strip()) >= 12}


def check(zip_path, env=os.environ, limit: int = LIMIT_BYTES) -> tuple[list[str], dict]:
    problems: list[str] = []
    size = os.path.getsize(zip_path)
    if size >= limit:
        problems.append(f"zip is {size / 1e6:.1f} MB, limit {limit / 1e6:.0f} MB")
    secrets = secret_values(env)
    with zipfile.ZipFile(zip_path) as z:
        files = [i for i in z.infolist() if not i.is_dir()]
        names = {i.filename for i in files}
        if "README.md" not in names:
            problems.append("README.md is not at the root of the zip")
        for info in files:
            p = PurePosixPath(info.filename)
            if p.name == ".env" or (p.name.startswith(".env.") and p.name != ".env.example"):
                problems.append(f"{info.filename}: environment file")
            if CACHE_PARTS & set(p.parts) or p.suffix in {".pyc", ".pyo"}:
                problems.append(f"{info.filename}: cache file")
            if p.suffix.lower() in VIDEO_SUFFIXES:
                problems.append(f"{info.filename}: video")
            data = z.read(info)
            for label, pattern in KEY_PATTERNS.items():
                if pattern.search(data):
                    problems.append(f"{info.filename}: looks like a secret ({label})")
            for name, value in secrets.items():
                if value in data:
                    problems.append(f"{info.filename}: contains the value of ${name}")
        largest = sorted(files, key=lambda i: i.file_size, reverse=True)[:3]
    stats = {
        "bytes": size,
        "files": len(files),
        "secret_names_checked": sorted(secrets),
        "largest": [(i.filename, i.file_size) for i in largest],
    }
    return problems, stats


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m lastseat.package <zip>")
        return 2
    problems, stats = check(args[0])
    print(f"{args[0]}: {stats['files']} files, {stats['bytes'] / 1e6:.1f} MB (limit {LIMIT_BYTES / 1e6:.0f} MB)")
    print("largest files: " + ", ".join(f"{n} ({s / 1e6:.1f} MB)" for n, s in stats["largest"]))
    names = stats["secret_names_checked"]
    print(f"secret values from the environment checked: {len(names)} ({', '.join(names) or 'none set'})")
    if problems:
        print(f"FAILED, {len(problems)} problem(s):")
        for p in problems:
            print("  " + p)
        return 1
    print("ok: README.md at root; no .env, caches or videos; no key patterns; no secret values")
    return 0


if __name__ == "__main__":
    sys.exit(main())
