"""Generate the practice control file, run it, and verify the outputs."""
import logging
from pathlib import Path

from winsteps_pipeline.config import load_config
from winsteps_pipeline.control_file import write_control_file
from winsteps_pipeline.runner import run_winsteps

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ROOT = Path(__file__).resolve().parent.parent
cfg = load_config(ROOT / "config" / "ministep_practice.yaml")
control = cfg.output_dir / "generated.con"
report = cfg.output_dir / "report.txt"

# Ask for the item and person tables by name so the parser can find them later
write_control_file(cfg, ROOT / "templates" / "winsteps_control.tpl", control,
                   request_output_files=True)

# The report is optional for now: the parser only needs the item and person files
run_winsteps(cfg, control, report, require_report=False)
print("Done. Outputs in", cfg.output_dir)