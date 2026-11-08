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
    assert set(s) == {"overview", "categories", "models", "results", "failures", "pilot_concurrency", "validation", "runtime"}
    assert "behave as expected" in s["validation"]


def test_grading_time_is_the_first_grade_not_a_later_regrade(tmp_path):
    v = tmp_path / "verdict.json"
    v.write_text('{"seconds": 90, "regraded_from_disk": true}', encoding="utf-8")
    assert report._original_seconds(v) == (90, False)
    (tmp_path / "verdict.prev.json").write_text('{"seconds": 60}', encoding="utf-8")
    assert report._original_seconds(v) == (60, True)


def test_overview_and_categories_add_up_per_model():
    runs = report.final_runs()
    overview = report.overview_section(runs).splitlines()[2:]
    categories = report.categories_section(runs).splitlines()[2:]
    assert len(overview) == len(categories) == len(runs)
    for o, c in zip(overview, categories):
        passed, graded = map(int, o.split(" | ")[2].split("/"))
        cells = c.split(" | ")
        failed, load, spec, conc, harness = map(int, cells[2:7])
        assert failed == graded - passed == load + spec + conc + harness
        assert o.split(" | ")[-1].rstrip(" |") == str(conc)
