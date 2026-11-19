from pathlib import Path

import pandas as pd
import pytest

from winsteps_pipeline.config import load_config, validate_data_file
from winsteps_pipeline.parse import parse_item_file, parse_person_file
from winsteps_pipeline.qc import QCThresholds, compare_item_measures, run_qc
from winsteps_pipeline.report import build_report_html, write_report

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "ministep_practice.yaml"
REAL_ITEMS = ROOT / "data" / "winsteps_output" / "practice_ifile.txt"
REAL_PERSONS = ROOT / "data" / "winsteps_output" / "practice_pfile.txt"


def _frames():
    items = pd.DataFrame([
        {"label": "Item05", "measure": -1.32, "se": .33, "infit": 1.08, "outfit": 1.34, "ptmeasure_corr": .23, "status": 1},
        {"label": "Item07", "measure": .03, "se": .27, "infit": 1.44, "outfit": 1.70, "ptmeasure_corr": .01, "status": 1},
        {"label": "<b>Odd</b>", "measure": 1.0, "se": .30, "infit": 1.0, "outfit": 1.0, "ptmeasure_corr": .40, "status": 1},
    ])
    persons = pd.DataFrame([
        {"label": "P003", "measure": 1.55, "score": 15.0, "count": 20.0, "infit": 1.57, "outfit": 1.92, "status": 1},
        {"label": "P001", "measure": -1.51, "score": 5.0, "count": 20.0, "infit": .88, "outfit": .65, "status": 1},
    ])
    return items, persons


def _report(**kwargs):
    cfg = load_config(CONFIG)
    items, persons = _frames()
    th = QCThresholds()
    flags = run_qc(items, persons, th=th)
    return build_report_html(cfg, items, persons, flags, th, generated_at="2026-11-19 10:00", **kwargs)


def test_report_shows_counts_flags_and_context():
    page = _report(sources={"Item file": "C:/secret/folder/practice_ifile.txt"})
    assert "Calibration QC summary" in page and "2026-11-19 10:00" in page
    assert "Item07" in page and "infit_high" in page and "ptmeasure_low" in page
    assert 'class="review"' in page and 'class="note"' in page      # Item07 review, Item05 note
    assert "P003" in page and "P001" not in page.split("Persons with flags")[1].split("About this report")[0]
    assert "infit_max = 1.3" in page                                 # thresholds are recorded
    assert "practice_ifile.txt" in page and "secret" not in page     # only file names are shown


def test_labels_are_escaped_so_data_cannot_inject_html():
    page = _report()
    assert "<b>Odd</b>" not in page and "&lt;b&gt;Odd&lt;/b&gt;" in page


def test_report_has_no_stray_missing_value_text():
    page = _report()
    for bad in (">nan<", ">NaN<", ">None<", "nan</td>", "None</td>"):
        assert bad not in page


def test_comparison_section_appears_only_when_given():
    items, _ = _frames()
    before = items.copy()
    before.loc[before["label"] == "Item07", "measure"] += 0.6
    assert "Comparison with an earlier run" not in _report()
    page = _report(comparison=compare_item_measures(items, before))
    assert "Comparison with an earlier run" in page and "Item07" in page


def test_write_report_creates_the_file(tmp_path):
    cfg = load_config(CONFIG)
    items, persons = _frames()
    th = QCThresholds()
    path = write_report(tmp_path / "out" / "qc_report.html", cfg, items, persons,
                        run_qc(items, persons, th=th), th)
    assert path.exists() and path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


@pytest.mark.skipif(not (REAL_ITEMS.exists() and REAL_PERSONS.exists()),
                    reason="save the practice output files in data/winsteps_output first")
def test_report_from_the_real_practice_run(tmp_path):
    cfg = load_config(CONFIG)
    items = parse_item_file(REAL_ITEMS, cfg=cfg)
    persons = parse_person_file(REAL_PERSONS, n_persons=validate_data_file(cfg))
    th = QCThresholds()
    path = write_report(tmp_path / "r.html", cfg, items, persons, run_qc(items, persons, th=th), th)
    page = path.read_text(encoding="utf-8")
    assert "Item07" in page and "<b>1</b>items to review" in page