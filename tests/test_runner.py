import dataclasses
import sys
from pathlib import Path

import pytest

from winsteps_pipeline import runner
from winsteps_pipeline.config import load_config
from winsteps_pipeline.runner import (WinstepsError, build_command, check_outputs,
                                      find_winsteps_exe, run_command)

ROOT = Path(__file__).resolve().parent.parent


# ---- tests of the building blocks (no WINSTEPS needed: Python is the stand-in program) ----

def test_run_command_captures_output_and_exit_code():
    result = run_command([sys.executable, "-c", "print('hello')"])
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_nonzero_exit_code_is_reported_not_raised_by_run_command():
    result = run_command([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert result.returncode == 3


def test_timeout_raises_a_clear_error():
    with pytest.raises(WinstepsError, match="did not finish"):
        run_command([sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)


def test_unknown_program_raises_a_clear_error():
    with pytest.raises(WinstepsError, match="Could not start"):
        run_command(["this_program_does_not_exist_12345"])


def test_missing_and_empty_outputs_are_detected(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    with pytest.raises(WinstepsError, match="missing"):
        check_outputs([tmp_path / "nope.txt"])
    with pytest.raises(WinstepsError, match="empty"):
        check_outputs([empty])


def test_exe_must_be_configured(monkeypatch):
    monkeypatch.delenv("WINSTEPS_EXE", raising=False)
    with pytest.raises(WinstepsError, match="WINSTEPS_EXE"):
        find_winsteps_exe()


def test_command_is_built_as_a_list_of_arguments():
    assert build_command("prog.exe", "a.con", "b.txt") == ["prog.exe", "BATCH=YES", "a.con", "b.txt"]


# ---- tests of run_winsteps itself, using a fake program ----

def _cfg_in(tmp_path):
    cfg = load_config(ROOT / "config" / "ministep_practice.yaml")
    return dataclasses.replace(cfg, output_dir=tmp_path / "out")     # frozen, so copy with a change


def _fake_program(monkeypatch, code):
    monkeypatch.setattr(runner, "build_command",
                        lambda exe, control, report: [sys.executable, "-c", code])


def test_stale_outputs_do_not_count_as_success(tmp_path, monkeypatch):
    cfg = _cfg_in(tmp_path)
    cfg.output_dir.mkdir()
    (cfg.output_dir / cfg.item_file).write_text("old items")          # left over from a previous run
    (cfg.output_dir / cfg.person_file).write_text("old persons")
    _fake_program(monkeypatch, "pass")                                 # a program that writes nothing
    with pytest.raises(WinstepsError, match="missing"):
        runner.run_winsteps(cfg, "x.con", tmp_path / "report.txt", exe=sys.executable)


def test_fresh_outputs_pass_and_report_can_be_optional(tmp_path, monkeypatch):
    cfg = _cfg_in(tmp_path)
    code = ("from pathlib import Path; "
            f"d = Path(r'{cfg.output_dir}'); "
            f"(d / '{cfg.item_file}').write_text('items'); "
            f"(d / '{cfg.person_file}').write_text('persons')")
    _fake_program(monkeypatch, code)
    result = runner.run_winsteps(cfg, "x.con", tmp_path / "report.txt",
                                 exe=sys.executable, require_report=False)
    assert result.returncode == 0
    with pytest.raises(WinstepsError, match="report"):                 # but required by default
        runner.run_winsteps(cfg, "x.con", tmp_path / "report.txt", exe=sys.executable)