import os
import subprocess
import sys
from pathlib import Path

import pytest
from pack_run_helper import plan_bytes, put_wav, scene

from scenevoice.cli.main import main


def test_pack_help_shows_plan_dir_shape_on_stdout(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["pack", "--help"])
    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "[PLAN] DIR" in captured.out.splitlines()[0]
    assert captured.err == ""


def test_top_level_help_lists_pack(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "pack" in capsys.readouterr().out


def test_installed_script_packs_plan_from_a_pipe(tmp_path):
    script = Path(os.path.dirname(sys.executable)) / "scenevoice"
    if not script.exists():
        pytest.skip("scenevoice console script is not installed")
    out = tmp_path / "out"
    out.mkdir()
    put_wav(out, 1, 24000)
    result = subprocess.run(
        [str(script), "pack", str(out)],
        input=plan_bytes([scene(1, "One")]),
        capture_output=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr.startswith(b"scenevoice pack: OK 1 scenes")
    assert (out / "scene_manifest.csv").exists()
