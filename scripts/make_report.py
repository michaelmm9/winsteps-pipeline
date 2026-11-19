"""Parse saved WINSTEPS output, run the QC checks, and write a one-page HTML summary."""
from pathlib import Path

from winsteps_pipeline.config import load_config, validate_data_file
from winsteps_pipeline.parse import parse_item_file, parse_person_file
from winsteps_pipeline.qc import QCThresholds, run_qc
from winsteps_pipeline.report import write_report

ROOT = Path(__file__).resolve().parent.parent
cfg = load_config(ROOT / "config" / "ministep_practice.yaml")
out = ROOT / "data" / "winsteps_output"
item_path = out / "practice_ifile.txt"
person_path = out / "practice_pfile.txt"

items = parse_item_file(item_path, cfg=cfg)
persons = parse_person_file(person_path, n_persons=validate_data_file(cfg))

thresholds = QCThresholds()
flags = run_qc(items, persons, th=thresholds)

report_path = write_report(cfg.output_dir / "qc_report.html", cfg, items, persons, flags, thresholds,
                           sources={"Item file": item_path, "Person file": person_path})
print("Report written to", report_path)