import sys

from line_markers_helper import (
    SMOKE_LINE_FRAMES,
    align,
    markers,
    pack,
    sha,
    smoke_dir,
    write_timings,
)
from pack_run_helper import put_wav, scene, write_plan

_SKIP = "scenevoice pack: NOTE scene {} line {}: marker skipped, no free frame\n"
_STALE = "scenevoice pack: NOTE scene {}: line timings stale, scene marker only\n"
_NOENTRY = "scenevoice pack: NOTE scene {}: no line timings entry, scene marker only\n"


def _ok(out, count):
    return f"scenevoice pack: OK {count} scenes written to {out}/scene_manifest.csv and {out}/resolve_timeline.otio\n"


def _plan(tmp_path, count):
    return write_plan(tmp_path, [scene(n, f"T{n}", "Hello.") for n in range(1, count + 1)])


def _out(tmp_path, frames):
    out = tmp_path / "out"
    out.mkdir()
    for n, f in enumerate(frames, 1):
        put_wav(out, n, f)
    return out


def test_fresh_timings_give_green_line_markers_at_the_expected_frames(tmp_path):
    plan, out = smoke_dir(tmp_path)
    align(plan, out, tmp_path)
    code, text = pack(plan, out)
    assert code == 0 and text == _ok(out, 2)
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
    assert code == 0 and text == _STALE.format(2) + _ok(out, 2)
    found = markers(out)
    assert [(f, c) for f, c, _ in found if c == "GREEN"] == [(6, "GREEN"), (110, "GREEN"), (297, "GREEN"), (345, "GREEN")]
    assert [f for f, c, _ in found if c == "BLUE"] == [0, 418]
    assert len(found) == 6


def test_rewritten_wav_makes_scene_stale_on_next_pack(tmp_path):
    plan, out = smoke_dir(tmp_path)
    align(plan, out, tmp_path)
    assert pack(plan, out) == (0, _ok(out, 2))
    (out / "scene_manifest.csv").unlink()
    (out / "resolve_timeline.otio").unlink()
    put_wav(out, 1, 410000)
    code, text = pack(plan, out)
    assert code == 0 and text == _STALE.format(1) + _ok(out, 2)
    assert sum(1 for _, c, _ in markers(out) if c == "GREEN") == 4


def test_skipped_marker_note_names_scene_and_line_before_ok(tmp_path):
    out = _out(tmp_path, [1500])
    write_timings(out, [(1, sha(out, 1), [0])])
    code, text = pack(_plan(tmp_path, 1), out)
    assert code == 0
    assert text == _SKIP.format(1, 1) + _ok(out, 1)
    assert [c for _, c, _ in markers(out)] == ["BLUE"]


def test_skipped_notes_follow_plan_then_line_order_around_stale_scene(tmp_path):
    out = _out(tmp_path, [1500, 24000, 1500])
    write_timings(
        out,
        [(1, sha(out, 1), [0, 0]), (2, "0" * 64, [0]), (3, sha(out, 3), [0])],
    )
    code, text = pack(_plan(tmp_path, 3), out)
    assert code == 0
    assert text == _SKIP.format(1, 1) + _SKIP.format(1, 2) + _STALE.format(2) + _SKIP.format(3, 1) + _ok(out, 3)


def test_missing_entry_stale_and_skipped_notes_keep_plan_order(tmp_path):
    out = _out(tmp_path, [24000, 1500, 24000])
    write_timings(out, [(2, sha(out, 2), [0]), (3, "0" * 64, [0])])
    code, text = pack(_plan(tmp_path, 3), out)
    assert code == 0
    assert text == _NOENTRY.format(1) + _SKIP.format(2, 1) + _STALE.format(3) + _ok(out, 3)


def test_notes_come_before_a_write_failure(tmp_path, monkeypatch):
    out = _out(tmp_path, [1500])
    write_timings(out, [(1, sha(out, 1), [0])])
    module = sys.modules["scenevoice.pack.write_pack_files"]
    real = module.os.replace
    calls = []

    def fake(src, dst, *a, **kw):
        calls.append(dst)
        if str(dst).endswith("resolve_timeline.otio"):
            raise OSError("injected")
        return real(src, dst, *a, **kw)

    monkeypatch.setattr(module.os, "replace", fake)
    code, text = pack(_plan(tmp_path, 1), out)
    assert len(calls) == 2, "positive control"
    lines = text.splitlines()
    assert code == 1 and len(lines) == 2
    assert lines[0] == _SKIP.format(1, 1).rstrip("\n")
    assert lines[1].startswith("scenevoice pack: FAIL ")


def test_two_fresh_directories_give_identical_timelines(tmp_path):
    first = smoke_dir(tmp_path, "a")
    second = smoke_dir(tmp_path, "b")
    for plan, out in (first, second):
        align(plan, out, tmp_path)
        assert pack(plan, out)[0] == 0
    assert (first[1] / "resolve_timeline.otio").read_bytes() == (second[1] / "resolve_timeline.otio").read_bytes()


def test_pack_leaves_the_timings_file_untouched(tmp_path):
    plan, out = smoke_dir(tmp_path)
    align(plan, out, tmp_path)
    path = out / "line_timings.json"
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    assert pack(plan, out)[0] == 0
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
