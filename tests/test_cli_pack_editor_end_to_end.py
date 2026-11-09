import sys
from pathlib import Path

from pack_run_helper import FakeStdin, plan_bytes, put_wav, scene, write_plan

from scenevoice.cli.main import main

_GOLDEN = Path(__file__).parent / "fixtures" / "resolve_timeline_two_scenes.otio"
_SCENES = [
    scene(1, "Café, au lait", "First sentence."),
    scene(2, 'The "big" day', "Second sentence."),
]
_MANIFEST = (
    'scene,label,file,duration_s\n'
    '1,"Café, au lait",audio/001.wav,2.100\n'
    '2,"The ""big"" day",audio/002.wav,5.144\n'
).encode()


def _out(tmp_path, second_frames=123456):
    out = tmp_path / "out"
    out.mkdir()
    put_wav(out, 1, 50400)
    put_wav(out, 2, second_frames)
    return out


_NOTE = "scenevoice pack: NOTE no line_timings.json, scene markers only\n"


def _ok_line(out):
    return (
        f"scenevoice pack: OK 2 scenes written to {out / 'scene_manifest.csv'}"
        f" and {out / 'resolve_timeline.otio'}\n"
    )


def test_editor_run_writes_manifest_and_golden_timeline(tmp_path, capsys):
    out = _out(tmp_path)
    code = main(["pack", "--editor", "resolve", str(write_plan(tmp_path, _SCENES)), str(out)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert captured.err == _NOTE + _ok_line(out)
    assert (out / "scene_manifest.csv").read_bytes() == _MANIFEST
    assert (out / "resolve_timeline.otio").read_bytes() == _GOLDEN.read_bytes()
    assert sorted(p.name for p in out.iterdir()) == [
        "audio",
        "resolve_timeline.otio",
        "scene_manifest.csv",
    ]


def test_editor_run_reads_plan_from_stdin(tmp_path, capsys, monkeypatch):
    out = _out(tmp_path)
    monkeypatch.setattr(sys, "stdin", FakeStdin(plan_bytes(_SCENES)))
    code = main(["pack", "--editor", "resolve", str(out)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert captured.err == _NOTE + _ok_line(out)
    assert (out / "resolve_timeline.otio").read_bytes() == _GOLDEN.read_bytes()


def test_rerun_fails_on_manifest_collision_with_files_unchanged(tmp_path, capsys):
    out = _out(tmp_path)
    plan = str(write_plan(tmp_path, _SCENES))
    assert main(["pack", "--editor", "resolve", plan, str(out)]) == 0
    capsys.readouterr()
    code = main(["pack", "--editor", "resolve", plan, str(out)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "scene_manifest.csv" in captured.err
    assert (out / "scene_manifest.csv").read_bytes() == _MANIFEST
    assert (out / "resolve_timeline.otio").read_bytes() == _GOLDEN.read_bytes()


def test_flagless_run_writes_only_the_manifest(tmp_path, capsys):
    out = _out(tmp_path)
    code = main(["pack", str(write_plan(tmp_path, _SCENES)), str(out)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err.endswith(f"written to {out / 'scene_manifest.csv'}\n")
    assert (out / "scene_manifest.csv").read_bytes() == _MANIFEST
    assert sorted(p.name for p in out.iterdir()) == ["audio", "scene_manifest.csv"]


def test_short_wav_fails_and_leaves_out_as_it_was(tmp_path, capsys):
    out = _out(tmp_path, second_frames=500)
    code = main(["pack", "--editor", "resolve", str(write_plan(tmp_path, _SCENES)), str(out)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "scene 2" in captured.err and "audio/002.wav" in captured.err
    assert sorted(p.name for p in out.iterdir()) == ["audio"]
