"""Pack through the CLI end to end: align then pack for Resolve, and the one true-subprocess run where the installed console script reads a plan from a pipe."""

import os
import sys
from pathlib import Path

import pytest
from align_run_helper import Fake, NoTerminal
from common_helper import run
from line_markers_helper import FIXTURE, SMOKE_LINE_FRAMES, markers, smoke_dir
from pack_run_helper import FakeStdin, plan_bytes, put_wav, scene, write_plan

from scenevoice.cli.main import main

_SCENES = [scene(1, "One"), scene(2, "Two, too")]


_EXPECTED = (
    b"scene,label,file,duration_s\n"
    b"1,One,audio/001.wav,1.000\n"
    b'2,"Two, too",audio/002.wav,2.000\n'
)


def _out(tmp_path, second=True):
    out = tmp_path / "out"
    out.mkdir()
    put_wav(out, 1, 24000)
    if second:
        put_wav(out, 2, 48000)
    return out


def test_two_positionals_plan_then_dir(tmp_path, capsys):
    out = _out(tmp_path)
    code = main(["pack", str(write_plan(tmp_path, _SCENES)), str(out)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert captured.err.endswith(f"written to {out / 'scene_manifest.csv'}\n")
    assert captured.err.startswith("scenevoice pack: OK 2 scenes")
    assert (out / "scene_manifest.csv").read_bytes() == _EXPECTED


def test_one_positional_reads_plan_from_stdin(tmp_path, capsys, monkeypatch):
    out = _out(tmp_path)
    monkeypatch.setattr(sys, "stdin", FakeStdin(plan_bytes(_SCENES)))
    code = main(["pack", str(out)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert captured.err.startswith("scenevoice pack: OK 2 scenes")
    assert (out / "scene_manifest.csv").read_bytes() == _EXPECTED


def test_missing_wav_fails_naming_scene_and_file(tmp_path, capsys):
    out = _out(tmp_path, second=False)
    code = main(["pack", str(write_plan(tmp_path, _SCENES)), str(out)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("scenevoice pack: FAIL")
    assert "scene 2" in captured.err and "audio/002.wav" in captured.err
    assert not (out / "scene_manifest.csv").exists()


def test_collision_fails_and_keeps_existing_manifest(tmp_path, capsys):
    out = _out(tmp_path)
    (out / "scene_manifest.csv").write_bytes(b"keep me")
    code = main(["pack", str(write_plan(tmp_path, _SCENES)), str(out)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("scenevoice pack: FAIL")
    assert "scene_manifest.csv" in captured.err
    assert (out / "scene_manifest.csv").read_bytes() == b"keep me"


def test_terminal_stdin_without_plan_fails(tmp_path, capsys, monkeypatch):
    out = _out(tmp_path)
    monkeypatch.setattr(sys, "stdin", FakeStdin(b"", tty=True))
    code = main(["pack", str(out)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("scenevoice pack: FAIL")
    assert not (out / "scene_manifest.csv").exists()


def test_single_positional_is_dir_even_with_empty_stdin(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", FakeStdin(b""))
    code = main(["pack", "out"])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("scenevoice pack: FAIL")


def test_double_dash_makes_weird_name_the_dir(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", FakeStdin(b""))
    code = main(["pack", "--", "-weird-dir"])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("scenevoice pack: FAIL")


def test_plan_stdout_piped_into_pack(tmp_path, capsys, monkeypatch):
    script = tmp_path / "script.md"
    script.write_text("# T\n\n## Scene 1: First\nHello there.\n\n## Scene 2: Second\nMore.\n")
    assert main(["plan", str(script)]) == 0
    plan_json = capsys.readouterr().out.encode("utf-8")
    out = _out(tmp_path)
    monkeypatch.setattr(sys, "stdin", FakeStdin(plan_json))
    code = main(["pack", str(out)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert captured.err.startswith("scenevoice pack: OK 2 scenes written to ")
    assert (out / "scene_manifest.csv").read_bytes() == (
        b"scene,label,file,duration_s\n1,Scene 1: First,audio/001.wav,1.000\n2,Scene 2: Second,audio/002.wav,2.000\n"
    )


@pytest.fixture(autouse=True)
def clean_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-key-value")
    monkeypatch.setattr(sys, "stdin", NoTerminal())


def test_align_then_pack_resolve_through_main(tmp_path, capsys):
    plan, out = smoke_dir(tmp_path)
    fake = Fake([FIXTURE.read_bytes(), FIXTURE.read_bytes()])
    assert main(["align", str(plan), str(out)], transcriber_factory=lambda key: fake) == 0
    first = capsys.readouterr()
    assert first.out == "" and "OK 2 scenes, 8 lines, 0 unmatched, 0 from synth record, 2 transcribed" in first.err
    assert main(["pack", "--editor", "resolve", str(plan), str(out)]) == 0
    second = capsys.readouterr()
    assert second.out == "" and "NOTE" not in second.err
    assert second.err.startswith("scenevoice pack: OK 2 scenes")
    assert sorted(p.name for p in out.iterdir()) == [
        "audio",
        "line_timings.json",
        "resolve_timeline.otio",
        "scene_manifest.csv",
    ]
    assert [f for f, _, _ in markers(out)] == sorted(SMOKE_LINE_FRAMES)


def test_installed_script_packs_plan_from_a_pipe(tmp_path):
    if not (Path(os.path.dirname(sys.executable)) / "scenevoice").exists():
        pytest.skip("scenevoice console script is not installed")
    out = tmp_path / "out"
    out.mkdir()
    put_wav(out, 1, 24000)
    result = run(["pack", str(out)], cwd=tmp_path, input=plan_bytes([scene(1, "One")]))
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr.startswith(b"scenevoice pack: OK 1 scenes")
    assert (out / "scene_manifest.csv").exists()
