"""README sections are generated from results/, replaced in place, idempotently."""

from lastseat import report


def test_write_fills_markers_idempotently_and_reports_missing_ones(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "sections", lambda: {"results": "| a | b |", "models": "m"})
    readme = tmp_path / "README.md"
    readme.write_text("intro\n<!-- BEGIN report:results -->\n<!-- END report:results -->\nend\n", encoding="utf-8")
    assert report.write(readme) == ["models"]
    first = readme.read_text(encoding="utf-8")
    assert first == "intro\n<!-- BEGIN report:results -->\n| a | b |\n<!-- END report:results -->\nend\n"
    report.write(readme)
    assert readme.read_text(encoding="utf-8") == first


def test_sections_come_from_the_results_directory():
    s = report.sections()
    assert set(s) == {"models", "results", "failures", "validation", "runtime"}
    assert "behave as expected" in s["validation"]
