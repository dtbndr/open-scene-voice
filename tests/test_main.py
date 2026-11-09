import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scenevoice.cli.main import main


def test_console_script_installed_next_to_interpreter():
    script = Path(os.path.dirname(sys.executable)) / "scenevoice"
    assert script.exists()


def test_cli_main_module_importable():
    module = importlib.import_module("scenevoice.cli.main")
    assert callable(module.main)


def test_main_without_command_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_plan_without_path_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        main(["plan"])
    assert exc.value.code == 2


def test_plan_with_extra_argument_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        main(["plan", "a", "b"])
    assert exc.value.code == 2


def test_top_level_help_mentions_plan(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "plan" in capsys.readouterr().out


def test_top_level_help_says_plan_emits_the_plan(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert "validate" not in out
    assert "print a script's scene plan as JSON" in out


def test_plan_help_mentions_file_path(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["plan", "--help"])
    assert exc.value.code == 0
    assert "file_path" in capsys.readouterr().out


def test_installed_script_help_lists_plan():
    script = Path(os.path.dirname(sys.executable)) / "scenevoice"
    result = subprocess.run(
        [str(script), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "plan" in result.stdout
