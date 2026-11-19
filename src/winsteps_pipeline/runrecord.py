"""Write a small JSON "run record" so a result can be traced and reproduced later."""
import dataclasses
import hashlib
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import pandas as pd


def file_sha256(path, chunk_size=1024 * 1024):
    """Fingerprint a file. Reads in chunks, so it is safe for very large files."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_info(repo_dir):
    """Return the current Git commit and whether there are uncommitted changes."""
    unknown = {"commit": "unknown", "uncommitted_changes": None}
    if shutil.which("git") is None or repo_dir is None:
        return unknown
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir,
                                capture_output=True, text=True, timeout=10)
        if commit.returncode != 0:
            return unknown
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir,
                                capture_output=True, text=True, timeout=10)
        return {"commit": commit.stdout.strip(),
                "uncommitted_changes": bool(status.stdout.strip())}
    except (OSError, subprocess.TimeoutExpired):
        return unknown


def _jsonable(value):
    """Paths become bare file names, so records do not contain user names or folder structure."""
    if isinstance(value, Path):
        return value.name
    return value


def build_run_record(cfg, thresholds, inputs, flags=None, repo_dir=None, created=None):
    """Assemble the record as a dictionary.

    inputs is a dict of description -> file path. Each file is listed with its size and SHA-256.
    """
    try:
        version = metadata.version("winsteps-pipeline")
    except metadata.PackageNotFoundError:
        version = "unknown"

    record = {
        "created_utc": created or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "project": cfg.name,
        "software": {
            "winsteps_pipeline": version,
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "platform": platform.platform(),
        },
        "git": git_info(repo_dir),
        "config": {k: _jsonable(v) for k, v in dataclasses.asdict(cfg).items()},
        "thresholds": dataclasses.asdict(thresholds),
        "inputs": {
            description: {"file": Path(p).name, "bytes": Path(p).stat().st_size,
                          "sha256": file_sha256(p)}
            for description, p in inputs.items()
        },
    }
    if flags is not None:
        record["results"] = {
            "flags_total": int(len(flags)),
            "review": int((flags["severity"] == "review").sum()),
            "note": int((flags["severity"] == "note").sum()),
        }
    return record


def write_run_record(path, *args, **kwargs):
    """Build the record and save it as JSON. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_run_record(*args, **kwargs), indent=2), encoding="utf-8")
    return path


def verify_inputs(record_path, inputs):
    """Check that input files still match a saved record. Returns a list of problems (empty = match)."""
    record = json.loads(Path(record_path).read_text(encoding="utf-8"))
    problems = []
    for description, p in inputs.items():
        saved = record["inputs"].get(description)
        if saved is None:
            problems.append(f"{description}: not in the record")
        elif not Path(p).exists():
            problems.append(f"{description}: file is missing")
        elif file_sha256(p) != saved["sha256"]:
            problems.append(f"{description}: contents changed since the record was written")
    return problems