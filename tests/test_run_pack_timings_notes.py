import io
import os
import sys

from pack_run_helper import FakeStdin, put_wav, scene, write_plan
from pack_timings_helper import MISSING, make_out, ok_line, run, timings_doc, wav_hash

from scenevoice.pack import run_pack

_STALE = "0" * 64
_GOLDEN = os.path.join(os.path.dirname(__file__), "fixtures", "resolve_timeline_two_scenes.otio")


def test_no_file_gives_missing_note_then_ok_and_exit_0(tmp_path):
    out = make_out(tmp_path)
    code, text = run(tmp_path, out)
    assert code == 0
    assert text == MISSING + ok_line(out)


def test_no_file_timeline_equals_ws23_golden(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    put_wav(out, 1, 50400)
    put_wav(out, 2, 123456)
    plan = write_plan(tmp_path, [scene(1, "Café, au lait", "First sentence."), scene(2, 'The "big" day', "Second sentence.")])
    assert run_pack(plan, FakeStdin(b""), out, io.StringIO(), "resolve") == 0
    with open(_GOLDEN, "rb") as handle:
        assert (out / "resolve_timeline.otio").read_bytes() == handle.read()


def test_fresh_scenes_give_no_note(tmp_path):
    out = make_out(tmp_path)
    (out / "line_timings.json").write_bytes(timings_doc([(1, wav_hash(out, 1)), (2, wav_hash(out, 2))]))
    code, text = run(tmp_path, out)
    assert code == 0
    assert text == ok_line(out)


def test_stale_scene_gives_note_naming_scene_then_ok(tmp_path):
    out = make_out(tmp_path)
    (out / "line_timings.json").write_bytes(timings_doc([(1, wav_hash(out, 1)), (2, _STALE)]))
    code, text = run(tmp_path, out)
    assert code == 0
    assert text == (
        "scenevoice pack: NOTE scene 2: line timings stale, scene marker only\n" + ok_line(out)
    )


def test_scene_without_entry_gives_note_naming_scene(tmp_path):
    out = make_out(tmp_path)
    (out / "line_timings.json").write_bytes(timings_doc([(2, wav_hash(out, 2))]))
    code, text = run(tmp_path, out)
    assert code == 0
    assert text == (
        "scenevoice pack: NOTE scene 1: no line timings entry, scene marker only\n" + ok_line(out)
    )


def test_empty_scenes_array_notes_every_scene_in_plan_order(tmp_path):
    out = make_out(tmp_path)
    (out / "line_timings.json").write_bytes(b'{"scenes": []}')
    code, text = run(tmp_path, out)
    assert code == 0
    lines = text.splitlines()
    assert lines[0].startswith("scenevoice pack: NOTE scene 1:")
    assert lines[1].startswith("scenevoice pack: NOTE scene 2:")
    assert lines[2].startswith("scenevoice pack: OK") and len(lines) == 3


def test_notes_follow_plan_order_even_if_file_is_reversed(tmp_path):
    out = make_out(tmp_path)
    (out / "line_timings.json").write_bytes(timings_doc([(2, _STALE), (1, _STALE)]))
    _, text = run(tmp_path, out)
    lines = text.splitlines()
    assert "scene 1" in lines[0] and "scene 2" in lines[1] and lines[2].startswith("scenevoice pack: OK")


def test_notes_precede_a_check_5_failure(tmp_path, monkeypatch):
    out = make_out(tmp_path)
    (out / "line_timings.json").write_bytes(timings_doc([(1, _STALE)]))
    module = sys.modules["scenevoice.pack.write_pack_files"]
    real = module.os.replace
    calls = []

    def fake(src, dst, *a, **kw):
        calls.append(dst)
        if str(dst).endswith("scene_manifest.csv"):
            raise OSError("injected")
        return real(src, dst, *a, **kw)

    monkeypatch.setattr(module.os, "replace", fake)
    code, text = run(tmp_path, out)
    assert calls, "positive control: rename attempted"
    assert code == 1
    lines = text.splitlines()
    assert len(lines) == 3
    assert "NOTE scene 1" in lines[0] and "NOTE scene 2" in lines[1]
    assert lines[2].startswith("scenevoice pack: FAIL ")


def test_missing_file_note_precedes_check_5_failure(tmp_path, monkeypatch):
    out = make_out(tmp_path)
    module = sys.modules["scenevoice.pack.write_pack_files"]

    def fake(src, dst, *a, **kw):
        raise OSError("injected")

    monkeypatch.setattr(module.os, "replace", fake)
    code, text = run(tmp_path, out)
    assert code == 1
    lines = text.splitlines()
    assert lines[0] == MISSING.rstrip("\n") and lines[1].startswith("scenevoice pack: FAIL ")


def test_freshness_comes_from_held_bytes_not_a_second_read(tmp_path, monkeypatch):
    out = make_out(tmp_path)
    held_hash = wav_hash(out, 1)
    (out / "line_timings.json").write_bytes(timings_doc([(1, held_hash), (2, wav_hash(out, 2))]))
    module = sys.modules["scenevoice.pack.check_line_timings"]
    real = module.read_line_timings_file
    calls = []

    def rewrite_then_read(directory):
        calls.append(directory)
        (out / "audio" / "001.wav").write_bytes((out / "audio" / "001.wav").read_bytes() + b"\x00\x00")
        return real(directory)

    monkeypatch.setattr(module, "read_line_timings_file", rewrite_then_read)
    code, text = run(tmp_path, out)
    assert calls, "positive control: the hook ran"
    assert wav_hash(out, 1) != held_hash, "positive control: the file on disk changed"
    assert code == 0
    assert text == ok_line(out)
