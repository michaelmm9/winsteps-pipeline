"""Run WINSTEPS (or Ministep) from Python and check that it produced its outputs."""
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class WinstepsError(RuntimeError):
    """Raised when the program cannot be found, fails, times out, or writes no output."""


@dataclass(frozen=True)
class RunResult:
    command: tuple
    returncode: int
    seconds: float
    stdout: str
    stderr: str


def find_winsteps_exe(explicit=None):
    """Locate the program. The path is machine-specific, so it is NOT stored in the
    project config; it comes from an argument or the WINSTEPS_EXE environment variable."""
    candidate = explicit or os.environ.get("WINSTEPS_EXE")
    if not candidate:
        raise WinstepsError(
            "No WINSTEPS program configured. Set the WINSTEPS_EXE environment "
            "variable to the full path of the executable.")
    path = Path(candidate)
    if not path.exists():
        raise WinstepsError(f"WINSTEPS program not found at: {path}")
    return path


def build_command(exe, control_file, report_file):
    """Build the command line as a list of arguments.

    ASSUMPTION TO VERIFY in the WINSTEPS manual: that a batch-style call takes
    BATCH=YES, then the control file, then the report file. Keeping this in its own
    function means a correction only has to be made in one place.
    """
    return [str(exe), "BATCH=YES", str(control_file), str(report_file)]


def run_command(command, timeout=300):
    """Run an external program and capture what it printed. Never uses the shell."""
    start = time.perf_counter()
    try:
        proc = subprocess.run(command, capture_output=True, text=True,
                              errors="replace", timeout=timeout)
    except FileNotFoundError as exc:
        raise WinstepsError(f"Could not start program: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise WinstepsError(f"Program did not finish within {timeout} seconds") from exc
    return RunResult(tuple(command), proc.returncode,
                     time.perf_counter() - start, proc.stdout, proc.stderr)


def check_outputs(paths):
    """Confirm every expected output file exists and is not empty.

    Do not trust the exit code alone: a program can exit cleanly without producing results.
    """
    problems = []
    for p in map(Path, paths):
        if not p.exists():
            problems.append(f"missing: {p}")
        elif p.stat().st_size == 0:
            problems.append(f"empty: {p}")
    if problems:
        raise WinstepsError("Expected output problems: " + "; ".join(problems))


def run_winsteps(cfg, control_file, report_file, exe=None, timeout=300, require_report=True):
    """Run one calibration and verify the outputs the pipeline needs.

    The item and person files are always required, because the parser reads them.
    The report file is required only if require_report is True.
    """
    exe_path = find_winsteps_exe(exe)
    command = build_command(exe_path, control_file, report_file)

    item_file = cfg.output_dir / cfg.item_file
    person_file = cfg.output_dir / cfg.person_file
    expected = [item_file, person_file]
    if require_report:
        expected.append(Path(report_file))

    # Delete old outputs first. Otherwise files left over from an earlier run could make a
    # failed run look successful, because the existence check cannot tell old from new.
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    for path in expected + [Path(report_file)]:
        Path(path).unlink(missing_ok=True)

    logger.info("Running: %s", " ".join(command))
    result = run_command(command, timeout=timeout)
    logger.info("Finished in %.1f s with exit code %s", result.seconds, result.returncode)

    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-500:]
        raise WinstepsError(f"Program exited with code {result.returncode}. Output: {tail}")

    check_outputs(expected)
    return result