import sys

import pytest
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


@pytest.mark.parametrize("argv", [["pack"], ["pack", "a", "b", "c"]])
def test_usage_errors_exit_2_with_empty_stdout(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
    assert capsys.readouterr().out == ""
