"""Run the QC checks on the saved practice output and print a summary."""
from pathlib import Path

import pandas as pd

from winsteps_pipeline.config import load_config, validate_data_file
from winsteps_pipeline.parse import parse_item_file, parse_person_file
from winsteps_pipeline.qc import run_qc, summarize

ROOT = Path(__file__).resolve().parent.parent
cfg = load_config(ROOT / "config" / "ministep_practice.yaml")
out = ROOT / "data" / "winsteps_output"

items = parse_item_file(out / "practice_ifile.txt", cfg=cfg)
persons = parse_person_file(out / "practice_pfile.txt", n_persons=validate_data_file(cfg))
flags = run_qc(items, persons)

pd.set_option("display.width", 170)
pd.set_option("display.max_colwidth", 70)
print(summarize(flags))
print()
print(flags[flags["severity"] == "review"][["kind", "label", "check", "value", "threshold", "message"]]
      .to_string(index=False))