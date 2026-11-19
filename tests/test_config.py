from pathlib import Path

import pytest

from winsteps_pipeline.config import ConfigError, load_config, validate_data_file

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "ministep_practice.yaml"


def test_practice_config_loads_and_data_matches():
    cfg = load_config(CONFIG)
    assert cfg.n_items == 20
    assert cfg.item_labels[0] == "Item01" and cfg.item_labels[-1] == "Item20"
    assert validate_data_file(cfg) == 70


def test_inconsistent_column_settings_are_rejected(tmp_path):
    text = CONFIG.read_text().replace("item_first_column: 9", "item_first_column: 10")
    bad = tmp_path / "config" / "bad.yaml"
    bad.parent.mkdir()
    bad.write_text(text)
    with pytest.raises(ConfigError, match="item_first_column"):
        load_config(bad, base_dir=ROOT)


def test_wrong_item_count_is_caught_in_data(tmp_path):
    text = CONFIG.read_text().replace("n_items: 20", "n_items: 22")
    bad = tmp_path / "config" / "bad.yaml"
    bad.parent.mkdir()
    bad.write_text(text)
    cfg = load_config(bad, base_dir=ROOT)
    with pytest.raises(ConfigError, match="expected 30"):
        validate_data_file(cfg)