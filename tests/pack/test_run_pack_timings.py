"""line_timings.json in a run: editor runs read it and fail on a bad file; plain runs never look. NOTE lines in an editor run: when each is written, in what order, and that they come before a failure.

The note wording is pinned by tests/pack/test_fresh_timings.py and the skipped-marker note
here; most cases below only look at which scene a line names. Line markers in editor runs end to end (align, then pack), and the NOTE order around skipped markers."""

import os
import re
import sys

import pytest
from line_markers_helper import (
    SMOKE_LINE_FRAMES,
    align,
    markers,
    pack,
    sha,
    smoke_dir,
    write_timings,
)
from pack_run_helper import (
    MISSING_NOTE,
    make_out,
    ok_line,
    put_wav,
    run,
    run_text,
    scene,
    snapshot,
    timings_doc,
    wav_hash,
    write_plan,
)


def _plant(out, kind):
    target = out / "line_timings.json"
    if kind == "malformed":
        target.write_text("{not json")
    elif kind == "dir":
        target.mkdir()
    elif kind == "dangling":
        os.symlink(out / "gone", target)
    return target


@pytest.mark.parametrize("kind", ["malformed", "dir"])
def test_bad_timings_file_fails_naming_it_with_no_note_and_writes_nothing(tmp_path, kind):
    out = make_out(tmp_path)
    _plant(out, kind)
    before = snapshot(out)
    code, text = run(tmp_path, out)
    assert code == 1
    assert text.startswith("scenevoice pack: FAIL ") and "line_timings.json" in text
    assert text.count("\n") == 1, "no NOTE precedes a timings failure"
    assert snapshot(out) == before


@pytest.mark.parametrize("kind", ["malformed", "dir", "dangling"])
def test_plain_run_never_reads_the_file(tmp_path, kind, monkeypatch):
    out = make_out(tmp_path)
    reference = make_out(tmp_path, "ref")
    module = sys.modules["scenevoice.pack.run_pack"]
    reader = sys.modules["scenevoice.pack.check_line_timings"]

    def boom(*args):
        raise AssertionError("plain run read the timings file")

    assert run_text(write_plan(tmp_path), reference)[0] == 0
    _plant(out, kind)
    monkeypatch.setattr(module, "check_line_timings", boom)
    monkeypatch.setattr(reader, "read_line_timings_file", boom)
    code, text = run_text(write_plan(tmp_path), out)
    assert code == 0
    assert text == f"scenevoice pack: OK 2 scenes written to {out}/scene_manifest.csv\n"
    assert (out / "scene_manifest.csv").read_bytes() == (reference / "scene_manifest.csv").read_bytes()
    assert not (out / "resolve_timeline.otio").exists()


STALE = "0" * 64


def _notes(text):
    return re.findall(r"^scenevoice pack: NOTE (scene \d+):", text, flags=re.M)


def test_no_file_gives_the_missing_note_then_ok(tmp_path):
    out = make_out(tmp_path)
    code, text = run(tmp_path, out)
    assert code == 0
    assert text == MISSING_NOTE + ok_line(out)


def test_fresh_scenes_give_no_note(tmp_path):
    out = make_out(tmp_path)
    (out / "line_timings.json").write_bytes(timings_doc([(1, wav_hash(out, 1)), (2, wav_hash(out, 2))]))
    assert run(tmp_path, out) == (0, ok_line(out))


@pytest.mark.parametrize(
    ("entries", "named"),
    [
        ([(1, "fresh"), (2, STALE)], ["scene 2"]),
        ([(2, "fresh")], ["scene 1"]),
        ([], ["scene 1", "scene 2"]),
        ([(2, STALE), (1, STALE)], ["scene 1", "scene 2"]),
    ],
    ids=["stale", "no-entry", "empty-scenes-array", "reversed-file-stale"],
)
def test_one_note_per_unusable_scene_in_plan_order_then_ok(tmp_path, entries, named):
    out = make_out(tmp_path)
    shaped = [(n, wav_hash(out, n) if h == "fresh" else h) for n, h in entries]
    (out / "line_timings.json").write_bytes(timings_doc(shaped))
    code, text = run(tmp_path, out)
    assert code == 0
    assert _notes(text) == named
    assert text.endswith(ok_line(out))


def _fail_rename(monkeypatch, ending):
    module = sys.modules["scenevoice.pack.write_pack_files"]
    real = module.os.replace
    calls = []

    def fake(src, dst, *a, **kw):
        calls.append(dst)
        if str(dst).endswith(ending):
            raise OSError("injected")
        return real(src, dst, *a, **kw)

    monkeypatch.setattr(module.os, "replace", fake)
    return calls


@pytest.mark.parametrize(
    ("ending", "renames"), [("scene_manifest.csv", 1), ("resolve_timeline.otio", 2)]
)
def test_notes_come_before_a_write_failure(tmp_path, monkeypatch, ending, renames):
    out = make_out(tmp_path)
    (out / "line_timings.json").write_bytes(timings_doc([(1, STALE)]))
    calls = _fail_rename(monkeypatch, ending)
    code, text = run(tmp_path, out)
    assert len(calls) == renames, "positive control: the renames up to the injected failure ran"
    assert code == 1
    lines = text.splitlines()
    assert len(lines) == 3
    assert "NOTE scene 1" in lines[0] and "NOTE scene 2" in lines[1]
    assert lines[2].startswith("scenevoice pack: FAIL ")


def test_missing_file_note_comes_before_a_write_failure(tmp_path, monkeypatch):
    out = make_out(tmp_path)
    _fail_rename(monkeypatch, "scene_manifest.csv")
    code, text = run(tmp_path, out)
    lines = text.splitlines()
    assert code == 1
    assert lines[0] == MISSING_NOTE.rstrip("\n") and lines[1].startswith("scenevoice pack: FAIL ")


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


_SKIP = "scenevoice pack: NOTE scene {} line {}: marker skipped, no free frame\n"


_STALE = "scenevoice pack: NOTE scene {}: line timings stale, scene marker only\n"


_NOENTRY = "scenevoice pack: NOTE scene {}: no line timings entry, scene marker only\n"


def _plan(tmp_path, count):
    return write_plan(tmp_path, [scene(n, f"T{n}", "Hello.") for n in range(1, count + 1)])


def test_fresh_timings_give_green_line_markers_at_the_expected_frames(tmp_path):
    plan, out = smoke_dir(tmp_path)
    align(plan, out, tmp_path)
    code, text = pack(plan, out)
    assert code == 0 and text == ok_line(out)
    found = markers(out)
    assert [f for f, _, _ in found] == sorted(SMOKE_LINE_FRAMES)
    greens = [(f, n) for f, c, n in found if c == "GREEN"]
    assert len(greens) == 8
    assert greens[0] == (6, "L1.1: Rome was burning, but one man refused to panic.")
    assert [f for f, _ in greens] == [6, 110, 297, 345, 424, 528, 715, 763]
    assert [n.split(":")[0] for _, n in greens] == ["L1.1", "L1.2", "L1.3", "L1.4", "L2.1", "L2.2", "L2.3", "L2.4"]
    assert [f for f, c, _ in found if c == "BLUE"] == [0, 418]


def test_stale_scene_keeps_scene_marker_only_others_keep_lines(tmp_path):
    plan, out = smoke_dir(tmp_path)
    align(plan, out, tmp_path)
    put_wav(out, 2, 409000)
    code, text = pack(plan, out)
    assert code == 0 and text == _STALE.format(2) + ok_line(out)
    found = markers(out)
    assert [(f, c) for f, c, _ in found if c == "GREEN"] == [(6, "GREEN"), (110, "GREEN"), (297, "GREEN"), (345, "GREEN")]
    assert [f for f, c, _ in found if c == "BLUE"] == [0, 418]
    assert len(found) == 6


def test_skipped_marker_note_names_scene_and_line_before_ok(tmp_path):
    out = make_out(tmp_path, frames=(1500,))
    write_timings(out, [(1, sha(out, 1), [0])])
    code, text = pack(_plan(tmp_path, 1), out)
    assert code == 0
    assert text == _SKIP.format(1, 1) + ok_line(out, 1)
    assert [c for _, c, _ in markers(out)] == ["BLUE"]


def test_skipped_notes_follow_plan_then_line_order_around_stale_scene(tmp_path):
    out = make_out(tmp_path, frames=(1500, 24000, 1500))
    write_timings(
        out,
        [(1, sha(out, 1), [0, 0]), (2, "0" * 64, [0]), (3, sha(out, 3), [0])],
    )
    code, text = pack(_plan(tmp_path, 3), out)
    assert code == 0
    assert text == _SKIP.format(1, 1) + _SKIP.format(1, 2) + _STALE.format(2) + _SKIP.format(3, 1) + ok_line(out, 3)


def test_missing_entry_stale_and_skipped_notes_keep_plan_order(tmp_path):
    out = make_out(tmp_path, frames=(24000, 1500, 24000))
    write_timings(out, [(2, sha(out, 2), [0]), (3, "0" * 64, [0])])
    code, text = pack(_plan(tmp_path, 3), out)
    assert code == 0
    assert text == _NOENTRY.format(1) + _SKIP.format(2, 1) + _STALE.format(3) + ok_line(out, 3)


def test_pack_leaves_the_timings_file_untouched(tmp_path):
    plan, out = smoke_dir(tmp_path)
    align(plan, out, tmp_path)
    path = out / "line_timings.json"
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    assert pack(plan, out)[0] == 0
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
