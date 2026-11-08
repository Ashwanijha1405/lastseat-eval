"""The submission-zip check refuses secrets, env files, caches, videos, oversize zips and a missing README."""

import zipfile

from lastseat import package

FAKE_KEY = "sk-or-v1-" + "0123456789abcdef" * 4


def make_zip(tmp_path, files):
    path = tmp_path / "s.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


def problems(tmp_path, files, env=None, limit=package.LIMIT_BYTES):
    return package.check(make_zip(tmp_path, files), env=env or {}, limit=limit)[0]


def test_a_clean_zip_passes(tmp_path):
    files = {"README.md": "# x", ".env.example": "OPENROUTER_API_KEY=\n", "lastseat/a.py": "import os\n"
             "KEY = os.environ.get('OPENROUTER_API_KEY')\n"}
    assert problems(tmp_path, files, env={"OPENROUTER_API_KEY": "x" * 40, "PATH": "/usr/bin"}) == []


def test_readme_must_be_at_the_root(tmp_path):
    assert problems(tmp_path, {"lastseat-eval/README.md": "# x"}) == ["README.md is not at the root of the zip"]


def test_env_files_caches_and_videos_are_refused(tmp_path):
    found = problems(tmp_path, {"README.md": "", ".env": "", "config/.env.local": "",
                                "lastseat/__pycache__/a.cpython-312.pyc": "", "demo.MP4": ""})
    assert len(found) == 4 and all(any(w in p for w in ("environment", "cache", "video")) for p in found)


def test_key_shaped_text_is_refused(tmp_path):
    assert problems(tmp_path, {"README.md": "", "log.txt": f"auth {FAKE_KEY}"}) == [
        "log.txt: looks like a secret (OpenRouter key)"]


def test_the_real_key_value_is_refused_by_name_without_printing_it(tmp_path):
    secret = "plain-looking-value-123"
    found = problems(tmp_path, {"README.md": "", "notes.txt": f"x {secret} y"}, env={"GEMINI_API_KEY": secret})
    assert found == ["notes.txt: contains the value of $GEMINI_API_KEY"]
    assert secret not in found[0]


def test_size_limit(tmp_path):
    assert problems(tmp_path, {"README.md": "x" * 1000}, limit=10)[0].startswith("zip is")
