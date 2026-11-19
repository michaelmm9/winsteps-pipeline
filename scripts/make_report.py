"""Parse saved WINSTEPS output, run the QC checks, and write the report and a run record."""
from pathlib import Path

from winsteps_pipeline.config import load_config, validate_data_file
from winsteps_pipeline.parse import parse_item_file, parse_person_file
from winsteps_pipeline.qc import QCThresholds, run_qc
from winsteps_pipeline.report import write_report
from winsteps_pipeline.runrecord import write_run_record

ROOT = Path(__file__).resolve().parent.parent
cfg = load_config(ROOT / "config" / "ministep_practice.yaml")
out = ROOT / "data" / "winsteps_output"
item_path = out / "practice_ifile.txt"
person_path = out / "practice_pfile.txt"

items = parse_item_file(item_path, cfg=cfg)
persons = parse_person_file(person_path, n_persons=validate_data_file(cfg))

thresholds = QCThresholds()
flags = run_qc(items, persons, th=thresholds)

sources = {"Item file": item_path, "Person file": person_path}
report_path = write_report(cfg.output_dir / "qc_report.html", cfg, items, persons, flags,
                           thresholds, sources=sources)

# The run record also fingerprints the control data and configuration, so the run can be traced
record_inputs = dict(sources, **{"Response data": cfg.data_file,
                                 "Config": ROOT / "config" / "ministep_practice.yaml"})
record_path = write_run_record(cfg.output_dir / "run_record.json", cfg, thresholds,
                               record_inputs, flags=flags, repo_dir=ROOT)
print("Report written to", report_path)
print("Run record written to", record_path)