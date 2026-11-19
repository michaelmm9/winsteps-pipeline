from pathlib import Path

import pytest

from winsteps_pipeline.config import load_config, validate_data_file
from winsteps_pipeline.parse import ParseError, parse_item_file, parse_person_file

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "ministep_practice.yaml"
REAL_ITEMS = ROOT / "data" / "winsteps_output" / "practice_ifile.txt"
REAL_PERSONS = ROOT / "data" / "winsteps_output" / "practice_pfile.txt"

# A short excerpt copied from a real Ministep run, so these tests do not depend on other files.
ITEM_EXCERPT = """\
ITEM  Ministep practice: simulated Rasch data  Nov 18 2026 21:21
;ENTRY MEASURE ST   COUNT    SCORE MODLSE IN.MSQ INZSTD OUTMSQ OUTZST  DISPL   PTMA WEIGHT OBSMA EXPMA PMA-E  RMSR    WMLE  INDF OUTDF G M R NAME
     1   -3.11  1    70.0     67.0    .60   1.02    .20    .98    .26   -.01    .17   1.00  95.7  95.7   .20   .20   -2.96  7.85  2.64 1 R . Item01
     6    -.41  1    70.0     47.0    .28   1.00    .00    .88   -.56    .00    .43   1.00  65.7  72.6   .41   .43    -.40 131.1 52.22 1 R . Item06
     7     .03  1    70.0     41.0    .27   1.44   3.67   1.70   3.84    .00    .01   1.00  57.1  69.4   .42   .53     .04 178.6 84.86 1 R . Item07
"""

PERSON_EXCERPT = """\
; PERSON  Ministep practice: simulated Rasch data  Nov 18 2026 21:21
;ENTRY MEASURE ST   COUNT    SCORE MODLSE IN.MSQ INZSTD OUTMSQ OUTZST  DISPL   PTMA WEIGHT OBSMA EXPMA PMA-E  RMSR    WMLE  INDF OUTDF NAME
     1   -1.51  1    20.0      5.0    .61    .88   -.25    .65   -.39    .00    .60   1.00  85.0  81.2   .52   .34   -1.46 17.68  4.60 P001
     3    1.55  1    20.0     15.0    .58   1.57   1.85   1.92   1.18    .01    .08   1.00  65.0  77.3   .43   .48    1.51 26.35  3.18 P003
     4     .92  1    20.0     13.0    .55   1.28   1.12   1.11    .37    .00    .35   1.00  65.0  75.8   .49   .46     .90 32.82  6.26 P004
     5     .92  1    20.0     13.0    .55    .70  -1.30    .55   -.77    .00    .67   1.00  85.0  75.8   .49   .34     .90 32.82  6.26 P005
"""


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return path


def test_item_excerpt_is_parsed_with_friendly_column_names(tmp_path):
    df = parse_item_file(_write(tmp_path, "i.txt", ITEM_EXCERPT))
    assert list(df["label"]) == ["Item01", "Item06", "Item07"]
    row = df[df["label"] == "Item07"].iloc[0]
    assert row["measure"] == 0.03 and row["infit"] == 1.44 and row["outfit"] == 1.70
    assert row["ptmeasure_corr"] == 0.01 and row["ptmeasure_exp"] == 0.42
    assert row["match_obs_pct"] == 57.1 and row["match_exp_pct"] == 69.4
    assert row["score"] == 41.0 and row["count"] == 70.0


def test_person_excerpt_shows_same_score_same_measure(tmp_path):
    df = parse_person_file(_write(tmp_path, "p.txt", PERSON_EXCERPT))
    assert len(df) == 4
    same_score = df[df["score"] == 13.0]
    assert list(same_score["label"]) == ["P004", "P005"]
    assert same_score["measure"].nunique() == 1          # sufficiency, visible in real output


def test_wrong_kind_of_file_is_rejected(tmp_path):
    with pytest.raises(ParseError, match="expected an item file"):
        parse_item_file(_write(tmp_path, "p.txt", PERSON_EXCERPT))
    with pytest.raises(ParseError, match="expected a person file"):
        parse_person_file(_write(tmp_path, "i.txt", ITEM_EXCERPT))


def test_a_short_row_is_rejected(tmp_path):
    bad = ITEM_EXCERPT.replace("1 R . Item06", "Item06")
    with pytest.raises(ParseError, match="expected 24 fields"):
        parse_item_file(_write(tmp_path, "bad.txt", bad))


def test_a_non_numeric_value_is_rejected(tmp_path):
    bad = ITEM_EXCERPT.replace("-3.11", "oops")
    with pytest.raises(ParseError, match="non-numeric"):
        parse_item_file(_write(tmp_path, "bad.txt", bad))


def test_labels_with_spaces_are_kept_whole(tmp_path):
    text = ITEM_EXCERPT.replace("Item07", "Item 07 reading")
    df = parse_item_file(_write(tmp_path, "i.txt", text))
    assert "Item 07 reading" in list(df["label"])


def test_missing_header_is_reported(tmp_path):
    with pytest.raises(ParseError, match="header"):
        parse_item_file(_write(tmp_path, "empty.txt", "ITEM nothing here\n"))


@pytest.mark.skipif(not (REAL_ITEMS.exists() and REAL_PERSONS.exists()),
                    reason="save the practice output files in data/winsteps_output first")
def test_real_practice_output_agrees_with_the_configuration():
    cfg = load_config(CONFIG)
    items = parse_item_file(REAL_ITEMS, cfg=cfg)                       # 20 rows, labels match config
    persons = parse_person_file(REAL_PERSONS, n_persons=validate_data_file(cfg))   # 70 rows
    assert abs(items["measure"].mean()) < 0.02                         # items are centered at 0
    row = items[items["label"] == "Item07"].iloc[0]
    assert (row["measure"], row["infit"], row["outfit"]) == (0.03, 1.44, 1.70)
    measured = persons[persons["status"] == 1]
    assert (measured.groupby("score")["measure"].nunique() == 1).all() # same score, same measure