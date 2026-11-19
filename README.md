# WINSTEPS pipeline prototype

A small prototype for making psychometric analysis runs repeatable. It generates a WINSTEPS
control file from a project configuration, picks up the item and person output files, parses
them, applies automated QC checks, and writes a one-page summary and a run record.

```
config (YAML) -> control-file template -> [run the program] -> parse -> QC flags -> report + run record
```

## Status

Prototype, built and tested on **simulated data** with the free Ministep. It is not validated
against real program data. Things confirmed so far: the generated control file reproduces the
hand-written practice file exactly; `IFILE=` and `PFILE=` produce the item and person files;
the parser reproduces values read from Ministep's own report.

Things to verify before relying on them:

-  The command-line (batch) call. On the one machine and version tested (free Ministep on
  Windows), it wrote fresh item and person files with no manual step, and their sizes match a
  manual run; a line-by-line comparison has not been done. The report file named in the call
  is still written empty and is not understood, so the pipeline does not require it.
  Behavior with the full WINSTEPS or other versions is untested. If the call fails, the
  fallback is to run the program yourself on the generated control file and let the pipeline
  process the output files.
- The meaning of several output columns and status codes. Unconfirmed columns keep their
  original names (lowercased) and are not interpreted. Check the WINSTEPS manual.
- QC thresholds are rule-of-thumb defaults and should be set per program.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
pytest
```

When updating `requirements.txt`, use `pip freeze --exclude-editable > requirements.txt` so the
local package itself is not written into the file.

## Layout

| Folder | Contents |
|---|---|
| `config/` | One YAML file per project: items, codes, columns, file names |
| `templates/` | The control-file template (`$placeholders`) |
| `src/winsteps_pipeline/` | `config`, `control_file`, `runner`, `parse`, `qc`, `report`, `runrecord` |
| `scripts/` | Entry points: `run_practice.py`, `make_report.py` |
| `data/` | Simulated practice data and saved output used as test fixtures |
| `tests/` | `pytest` tests |
| `outputs/` | Generated results (not committed) |

## Typical workflow

1. Describe the project in `config/<project>.yaml`. The loader checks the settings against each
   other and against the data file, and fails with a clear message if they disagree.
2. Generate the control file (`write_control_file` in `control_file.py`).
3. Run it in WINSTEPS (or Ministep). Make sure the control file requests `IFILE=` and `PFILE=`.
4. Save the item and person files in `data/winsteps_output/`.
5. `python scripts\make_report.py` writes `outputs/<project>/qc_report.html` and `run_record.json`.

## Adding a project

Copy an existing YAML in `config/`, change the values, point `data.file` at the new data, and
run the tests. Nothing in `src/` should need to change. If it does, treat that as a sign a
setting is missing from the configuration.

## Data policy

Only simulated data is committed. Real response data and real output must never be added to
the repository, even a private one. `outputs/` is ignored by Git.

## Contributing

- Work on a branch, run `pytest` before committing, and write commit messages that say what
  changed and why.
- Flags are prompts for review. Nothing in this project decides whether an item or person is
  kept; that is a psychometrician's judgment.