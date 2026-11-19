"""Parse WINSTEPS item (IFILE) and person (PFILE) output into pandas DataFrames."""
import re
from pathlib import Path

import pandas as pd


class ParseError(ValueError):
    """Raised when an output file does not look the way the parser expects."""


# These columns stay as text. Every other column must be numeric.
TEXT_COLUMNS = {"G", "M", "R", "NAME"}

# Friendlier names for the columns whose meaning we confirmed against the printed report.
# Any other column is kept, with its name lowercased (for example DISPL becomes displ).
RENAME = {
    "ENTRY": "entry",
    "MEASURE": "measure",
    "ST": "status",
    "COUNT": "count",
    "SCORE": "score",
    "MODLSE": "se",
    "IN.MSQ": "infit",
    "INZSTD": "infit_z",
    "OUTMSQ": "outfit",
    "OUTZST": "outfit_z",
    "PTMA": "ptmeasure_corr",
    "PMA-E": "ptmeasure_exp",
    "OBSMA": "match_obs_pct",
    "EXPMA": "match_exp_pct",
    "NAME": "label",
}


def _clean_name(name):
    return RENAME.get(name, re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"))


def read_winsteps_table(path):
    """Read an IFILE or PFILE into a DataFrame.

    Layout handled: a title line, a header line beginning ';ENTRY', then one row per
    item or person with whitespace-separated fields and the label in the last column.
    Lines starting with ';' are treated as comments. The label may contain spaces,
    because everything after the last fixed column is kept together as the label.
    The returned DataFrame has df.attrs['kind'] set to 'ITEM' or 'PERSON'.
    """
    path = Path(path)
    if not path.exists():
        raise ParseError(f"File not found: {path}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    header_idx = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith(";ENTRY")), None)
    if header_idx is None:
        raise ParseError(f"{path.name}: no header line starting with ';ENTRY' was found")

    title = next((ln for ln in lines[:header_idx] if ln.strip()), "")
    words = title.lstrip("; ").split()
    kind = words[0].upper() if words else ""

    names = lines[header_idx].lstrip().lstrip(";").split()
    rows = []
    for line_no, line in enumerate(lines[header_idx + 1:], start=header_idx + 2):
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        parts = line.split(None, len(names) - 1)     # the last field keeps any spaces
        if len(parts) != len(names):
            raise ParseError(
                f"{path.name} line {line_no}: expected {len(names)} fields, found {len(parts)}")
        rows.append(parts)
    if not rows:
        raise ParseError(f"{path.name}: no data rows found")

    df = pd.DataFrame(rows, columns=names)
    for col in df.columns:
        if col not in TEXT_COLUMNS:
            try:
                df[col] = pd.to_numeric(df[col])
            except ValueError as exc:
                raise ParseError(f"{path.name}: column {col} has a non-numeric value ({exc})") from exc

    df.columns = [_clean_name(c) for c in df.columns]
    df.attrs["kind"] = kind
    return df


def parse_item_file(path, cfg=None):
    """Parse an item file. If cfg is given, also check the item count and labels."""
    df = read_winsteps_table(path)
    if df.attrs["kind"] != "ITEM":
        raise ParseError(f"{Path(path).name}: expected an item file, found '{df.attrs['kind']}'")
    if cfg is not None:
        if len(df) != cfg.n_items:
            raise ParseError(f"Item file has {len(df)} rows, configuration says {cfg.n_items}")
        if list(df["label"]) != cfg.item_labels:
            raise ParseError("Item labels in the output do not match the configuration")
    return df


def parse_person_file(path, n_persons=None):
    """Parse a person file. If n_persons is given, also check the row count."""
    df = read_winsteps_table(path)
    if df.attrs["kind"] != "PERSON":
        raise ParseError(f"{Path(path).name}: expected a person file, found '{df.attrs['kind']}'")
    if n_persons is not None and len(df) != n_persons:
        raise ParseError(f"Person file has {len(df)} rows, expected {n_persons}")
    return df