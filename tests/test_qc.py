from pathlib import Path

import pandas as pd
import pytest

from winsteps_pipeline.config import load_config, validate_data_file
from winsteps_pipeline.parse import parse_item_file, parse_person_file
from winsteps_pipeline.qc import (compare_item_measures, flag_items, flag_persons,
                                  run_qc, summarize)

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "ministep_practice.yaml"
REAL_ITEMS = ROOT / "data" / "winsteps_output" / "practice_ifile.txt"
REAL_PERSONS = ROOT / "data" / "winsteps_output" / "practice_pfile.txt"


def _item(label="Item99", infit=1.0, outfit=1.0, corr=0.40, se=0.30, status=1, measure=0.0):
    return {"label": label, "infit": infit, "outfit": outfit, "ptmeasure_corr": corr,
            "se": se, "status": status, "measure": measure}


def _person(label="P999", infit=1.0, outfit=1.0, score=10.0, count=20.0, status=1):
    return {"label": label, "infit": infit, "outfit": outfit, "score": score,
            "count": count, "status": status}


def _checks(flags):
    return {(r.check, r.severity) for r in flags.itertuples()}


def test_a_clean_item_has_no_flags():
    assert flag_items(pd.DataFrame([_item()])).empty


def test_item07_like_row_is_flagged_for_review():
    flags = flag_items(pd.DataFrame([_item("Item07", infit=1.44, outfit=1.70, corr=0.01)]))
    assert _checks(flags) == {("infit_high", "review"), ("outfit_high", "review"),
                              ("ptmeasure_low", "review")}


def test_outfit_alone_is_only_a_note():
    flags = flag_items(pd.DataFrame([_item("Item05", infit=1.08, outfit=1.34)]))
    assert _checks(flags) == {("outfit_high", "note")}


def test_negative_correlation_points_to_the_key():
    flags = flag_items(pd.DataFrame([_item(corr=-0.2)]))
    row = flags[flags["check"] == "ptmeasure_negative"].iloc[0]
    assert row["severity"] == "review" and "key" in row["message"]


def test_overfit_and_imprecision_are_notes():
    flags = flag_items(pd.DataFrame([_item(infit=0.55, outfit=0.52, se=0.60)]))
    assert _checks(flags) == {("infit_low", "note"), ("outfit_low", "note"), ("se_high", "note")}


def test_person_checks_use_their_own_thresholds_and_flag_extremes():
    persons = pd.DataFrame([
        _person("P003", infit=1.57, outfit=1.92),     # clearly noisy
        _person("P004", infit=1.28, outfit=1.11),     # below the person cutoff of 1.5
        _person("P020", score=20.0, count=20.0),      # perfect score
    ])
    flags = flag_persons(persons)
    assert _checks(flags[flags["label"] == "P003"]) == {("infit_high", "review"), ("outfit_high", "review")}
    assert flags[flags["label"] == "P004"].empty
    assert _checks(flags[flags["label"] == "P020"]) == {("extreme_score", "note")}


def test_drift_is_judged_after_removing_the_typical_shift():
    before = pd.DataFrame({"label": ["A", "B", "C", "D"], "measure": [-1.0, 0.0, 1.0, 2.0]})
    now = pd.DataFrame({"label": ["A", "B", "C", "D"], "measure": [-1.5, -0.5, 0.5, 2.1]})
    # Everything moved by -0.5 except D, which moved by +0.1, so only D deviates from the shift
    flags, table = compare_item_measures(now, before)
    assert list(flags["label"]) == ["D"] and flags.iloc[0]["check"] == "drift"
    assert abs(table["diff"].median() - (-0.5)) < 1e-9


def test_new_and_missing_items_are_reported():
    before = pd.DataFrame({"label": ["A", "B"], "measure": [0.0, 1.0]})
    now = pd.DataFrame({"label": ["B", "C"], "measure": [1.0, 2.0]})
    flags, _ = compare_item_measures(now, before)
    assert _checks(flags) == {("new_item", "note"), ("missing_item", "review")}


def test_run_qc_lists_review_flags_first_and_summarizes():
    items = pd.DataFrame([_item("Item05", infit=1.08, outfit=1.34),
                          _item("Item07", infit=1.44, outfit=1.70, corr=0.01)])
    persons = pd.DataFrame([_person("P001")])
    flags = run_qc(items, persons)
    assert flags.iloc[0]["severity"] == "review"
    assert flags.iloc[-1]["severity"] == "note"
    assert summarize(flags).loc["item", "review"] == 3


@pytest.mark.skipif(not (REAL_ITEMS.exists() and REAL_PERSONS.exists()),
                    reason="save the practice output files in data/winsteps_output first")
def test_real_practice_run_flags_only_the_planted_item_for_review():
    cfg = load_config(CONFIG)
    items = parse_item_file(REAL_ITEMS, cfg=cfg)
    persons = parse_person_file(REAL_PERSONS, n_persons=validate_data_file(cfg))
    flags = run_qc(items, persons)
    review_items = flags[(flags["kind"] == "item") & (flags["severity"] == "review")]
    assert set(review_items["label"]) == {"Item07"}