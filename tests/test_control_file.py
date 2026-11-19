from pathlib import Path

from winsteps_pipeline.config import load_config
from winsteps_pipeline.control_file import render_control_file, write_control_file

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "ministep_practice.yaml"
TEMPLATE = ROOT / "templates" / "winsteps_control.tpl"
ORIGINAL = ROOT / "data" / "practice" / "ministep_practice.con"


def test_generated_file_matches_the_hand_written_original():
    """Parity test: the new system must reproduce the file we ran in Ministep."""
    cfg = load_config(CONFIG)
    generated = render_control_file(cfg, TEMPLATE)
    assert generated == ORIGINAL.read_text()        # read_text normalizes line endings


def test_output_file_lines_are_added_only_when_requested():
    cfg = load_config(CONFIG)
    plain = render_control_file(cfg, TEMPLATE)
    with_outputs = render_control_file(cfg, TEMPLATE, request_output_files=True)
    assert "IFILE" not in plain
    assert "IFILE = " in with_outputs and "PFILE = " in with_outputs
    assert with_outputs.index("IFILE") < with_outputs.index("&END")


def test_data_keyword_replaces_embedded_data():
    cfg = load_config(CONFIG)
    text = render_control_file(cfg, TEMPLATE, embed_data=False)
    assert "DATA = " in text
    assert text.rstrip().endswith("END NAMES")


def test_write_control_file_creates_the_file(tmp_path):
    cfg = load_config(CONFIG)
    dest = tmp_path / "out" / "practice.con"
    assert write_control_file(cfg, TEMPLATE, dest) == 70
    assert dest.exists()