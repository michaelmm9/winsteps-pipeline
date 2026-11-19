import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from winsteps_pipeline.config import load_config
from winsteps_pipeline.qc import QCThresholds
from winsteps_pipeline.runrecord import (build_run_record, file_sha256, git_info,
                                         verify_inputs, write_run_record)

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "ministep_practice.yaml"


def _inputs(tmp_path):
    f = tmp_path / "secret_folder" / "items.txt"
    f.parent.mkdir()
    f.write_text("some output")
    return {"Item file": f}


def test_file_sha256_matches_the_standard_library(tmp_path):
    f = tmp_path / "x.txt"
    f.write_bytes(b"hello world")
    assert file_sha256(f) == hashlib.sha256(b"hello world").hexdigest()


def test_record_contains_what_is_needed_to_trace_a_run(tmp_path):
    cfg = load_config(CONFIG)
    flags = pd.DataFrame({"severity": ["review", "note", "note"]})
    record = build_run_record(cfg, QCThresholds(), _inputs(tmp_path), flags=flags,
                              repo_dir=tmp_path, created="2026-11-19 10:00:00")
    assert record["created_utc"] == "2026-11-19 10:00:00" and record["project"] == "ministep_practice"
    assert record["software"]["python"] and record["software"]["pandas"]
    assert record["thresholds"]["infit_max"] == 1.3 and record["config"]["n_items"] == 20
    assert record["inputs"]["Item file"]["file"] == "items.txt"
    assert len(record["inputs"]["Item file"]["sha256"]) == 64
    assert record["results"] == {"flags_total": 3, "review": 1, "note": 2}


def test_record_holds_file_names_not_folder_paths(tmp_path):
    cfg = load_config(CONFIG)
    path = write_run_record(tmp_path / "run_record.json", cfg, QCThresholds(), _inputs(tmp_path))
    text = path.read_text(encoding="utf-8")
    assert "secret_folder" not in text and str(ROOT) not in text
    assert json.loads(text)["project"] == "ministep_practice"


def test_git_info_is_unknown_outside_a_repository(tmp_path):
    assert git_info(tmp_path)["commit"] == "unknown"


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_git_info_reports_commit_and_uncommitted_changes(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    git("init")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("one")
    git("add", ".")
    git("commit", "-m", "first")
    info = git_info(tmp_path)
    assert len(info["commit"]) == 40 and info["uncommitted_changes"] is False
    (tmp_path / "a.txt").write_text("two")
    assert git_info(tmp_path)["uncommitted_changes"] is True


def test_verify_inputs_detects_a_changed_file(tmp_path):
    cfg = load_config(CONFIG)
    inputs = _inputs(tmp_path)
    record = write_run_record(tmp_path / "r.json", cfg, QCThresholds(), inputs)
    assert verify_inputs(record, inputs) == []
    inputs["Item file"].write_text("tampered")
    problems = verify_inputs(record, inputs)
    assert len(problems) == 1 and "changed" in problems[0]