"""load and validate a project configuration"""
from dataclasses import dataclass
from pathlib import Path

import yaml

class ConfigError(ValueError):
    """Raised when a configuration is invalid"""

@dataclass(frozen=True)
class ProjectConfig:
    name: str
    title: str
    data_file: Path
    n_items: int
    person_label_start: int
    person_label_length: int
    item_first_column: int
    codes: str
    label_prefix: str
    label_width: int
    output_dir: Path
    item_file: str
    person_file: str

    @property
    def item_labels(self):
        """Item labels such as Item01...Item20, built from the settings."""
        return [
            f"{self.label_prefix}{i:0{self.label_width}d}"
            for i in range(1, self.n_items + 1)
        ]

    @property
    def record_length(self):
        """Expected length of every data line: label area plus one column per item."""
        return self.item_first_column - 1 + self.n_items

def _require(section, key, where):
    """Fetch a required key, with a clear error if it is missing."""
    if not isinstance(section, dict) or key not in section:
        raise ConfigError(f"Missing required setting '{where}.{key}'")
    return section[key]

def load_config(path, base_dir=None):
    """Read a YAML file and return a validated ProjectConfig.

    File paths in the YAML are resolved relative to base_dir
    (default: the project root, two levels above the YAML file).
    """
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError("Config file is empty or not a mapping")

    base = Path(base_dir) if base_dir else path.resolve().parent.parent

    project = _require(raw, "project", "")
    data = _require(raw, "data", "")
    items = _require(raw, "items", "")
    output = _require(raw, "output", "")

    cfg = ProjectConfig(
        name=str(_require(project, "name", "project")),
        title=str(_require(project, "title", "project")),
        data_file=base / _require(data, "file", "data"),
        n_items=_require(data, "n_items", "data"),
        person_label_start=_require(data, "person_label_start", "data"),
        person_label_length=_require(data, "person_label_length", "data"),
        item_first_column=_require(data, "item_first_column", "data"),
        codes=str(_require(data, "codes", "data")),
        label_prefix=str(_require(items, "label_prefix", "items")),
        label_width=_require(items, "label_width", "items"),
        output_dir=base / _require(output, "directory", "output"),
        item_file=str(_require(output, "item_file", "output")),
        person_file=str(_require(output, "person_file", "output")),
    )
    _validate(cfg)
    return cfg


def _validate(cfg):
    """Check settings for consistency before anything is generated or run."""
    for field in ("n_items", "person_label_start", "person_label_length",
                  "item_first_column", "label_width"):
        value = getattr(cfg, field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ConfigError(f"'{field}' must be a positive integer, got {value!r}")

    if not cfg.codes or len(set(cfg.codes)) != len(cfg.codes):
        raise ConfigError(f"'codes' must be non-empty with no repeated characters: {cfg.codes!r}")

    expected = cfg.person_label_start + cfg.person_label_length
    if cfg.item_first_column != expected:
        raise ConfigError(
            f"item_first_column ({cfg.item_first_column}) does not match "
            f"person_label_start + person_label_length ({expected})")


def validate_data_file(cfg):
    """Check the data file against the configuration. Returns the number of records."""
    if not cfg.data_file.exists():
        raise ConfigError(f"Data file not found: {cfg.data_file}")

    n_records = 0
    with cfg.data_file.open(encoding="utf-8") as f:   # line by line: safe for huge files
        for line_no, line in enumerate(f, start=1):
            line = line.rstrip("\r\n")
            if not line:
                continue
            n_records += 1
            if len(line) != cfg.record_length:
                raise ConfigError(
                    f"Line {line_no}: length {len(line)}, expected {cfg.record_length}")
            responses = line[cfg.item_first_column - 1:]
            bad = set(responses) - set(cfg.codes)
            if bad:
                raise ConfigError(
                    f"Line {line_no}: response codes {sorted(bad)} not in '{cfg.codes}'")
    if n_records == 0:
        raise ConfigError("Data file has no records")
    return n_records