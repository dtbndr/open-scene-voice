"""Order in which run_pack reports failures. Each case makes two checks fail at once.

Where a case asserts that the losing check is reachable, the winner is chosen by order and
not by the loser passing; the rest rely on the loser's message being absent. Mutants: scripts/mutants/pack/run_pack_*_before_*, *_after_*.
"""

import pytest
from pack_run_helper import make_out, put_wav, run, run_text, scene, write_plan

from scenevoice.pack import (
    check_no_collision,
    check_no_timeline_collision,
    check_pack_audio_dir,
    check_pack_dir,
)

MANIFEST = "scene_manifest.csv"
TIMELINE = "resolve_timeline.otio"


@pytest.mark.parametrize("editor", [None, "resolve"], ids=["plain", "editor"])
def test_bad_plan_beats_missing_dir(tmp_path, editor):
    plan = tmp_path / "plan.json"
    plan.write_bytes(b"not json")
    missing = tmp_path / "missing"
    assert check_pack_dir(missing) is not None
    code, text = run_text(plan, missing, editor)
    assert code == 1 and text.startswith("scenevoice pack: FAIL ")
    assert "does not exist" not in text
    assert not missing.exists()


def test_bad_plan_beats_an_existing_timeline_in_an_editor_run(tmp_path):
    out = make_out(tmp_path)
    (out / TIMELINE).write_bytes(b"t")
    assert check_no_timeline_collision(out) is not None
    plan = tmp_path / "plan.json"
    plan.write_bytes(b"not json")
    code, text = run_text(plan, out, "resolve")
    assert code == 1 and text.startswith("scenevoice pack: FAIL ")
    assert "resolve_timeline" not in text
    assert (out / TIMELINE).read_bytes() == b"t"


def test_dir_check_beats_manifest_check(tmp_path):
    # DIR is a file: the manifest check would also fail (lstat under a file raises ENOTDIR).
    not_dir = tmp_path / "afile"
    not_dir.write_bytes(b"x")
    assert check_no_collision(not_dir) is not None
    code, text = run_text(write_plan(tmp_path), not_dir)
    assert code == 1
    assert "not a directory" in text and MANIFEST not in text


def test_dir_check_beats_audio_dir_check(tmp_path):
    not_dir = tmp_path / "afile"
    not_dir.write_bytes(b"x")
    assert check_pack_audio_dir(not_dir) is not None
    code, text = run_text(write_plan(tmp_path), not_dir)
    assert code == 1
    assert f"{not_dir}: not a directory" in text and "/audio" not in text


def test_audio_dir_check_beats_manifest_collision(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / MANIFEST).write_bytes(b"old")
    assert check_no_collision(out) is not None
    code, text = run_text(write_plan(tmp_path, [scene(1)]), out)
    assert code == 1
    assert f"{out}/audio" in text and MANIFEST not in text


def test_manifest_collision_beats_missing_wav(tmp_path):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    (out / MANIFEST).write_bytes(b"keep")
    code, text = run_text(write_plan(tmp_path, [scene(1)]), out)
    assert code == 1
    assert MANIFEST in text and "001.wav" not in text
    assert (out / MANIFEST).read_bytes() == b"keep"


@pytest.mark.parametrize(
    ("invalid", "missing", "expected", "unexpected"),
    [(3, 2, "002", "003"), (1, 2, "001", "002")],
    ids=["missing-then-later-invalid", "invalid-then-later-missing"],
)
def test_first_wav_failure_in_plan_order_is_reported(tmp_path, invalid, missing, expected, unexpected):
    out = make_out(tmp_path, frames=())
    for n in (1, 2, 3):
        if n not in (invalid, missing):
            put_wav(out, n)
    (out / "audio").mkdir(exist_ok=True)
    (out / "audio" / f"{invalid:03d}.wav").write_bytes(b"not a wav")
    code, text = run_text(write_plan(tmp_path, [scene(1), scene(2), scene(3)]), out)
    assert code == 1
    assert f"audio/{expected}.wav" in text and f"audio/{unexpected}.wav" not in text
    assert not (out / MANIFEST).exists()


def _timeline_with(tmp_path, **kwargs):
    out = make_out(tmp_path, **kwargs)
    (out / TIMELINE).write_bytes(b"t")
    return out


def test_manifest_collision_beats_timeline_collision(tmp_path):
    out = _timeline_with(tmp_path)
    (out / MANIFEST).write_bytes(b"m")
    assert check_no_timeline_collision(out) is not None
    code, text = run(tmp_path, out)
    assert code == 1 and MANIFEST in text and "resolve_timeline" not in text


def test_audio_dir_check_beats_timeline_collision(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / TIMELINE).write_bytes(b"t")
    code, text = run(tmp_path, out)
    assert code == 1 and "audio" in text and "resolve_timeline" not in text


@pytest.mark.parametrize(
    ("frames", "beaten"),
    [((24000,), "002.wav"), ((999, 999), "001.wav")],
    ids=["missing-wav", "zero-frame-scene"],
)
def test_timeline_collision_beats_wav_failures_and_keeps_the_directory(tmp_path, frames, beaten):
    out = _timeline_with(tmp_path, frames=frames)
    before = _snapshot_bytes(out)
    code, text = run(tmp_path, out)
    assert code == 1 and TIMELINE in text and beaten not in text
    assert _snapshot_bytes(out) == before


def test_timeline_collision_beats_bad_line_timings(tmp_path):
    out = _timeline_with(tmp_path)
    (out / "line_timings.json").write_text("{not json")
    code, text = run(tmp_path, out)
    assert code == 1
    assert TIMELINE in text and "line_timings.json" not in text


def test_wav_failure_beats_bad_line_timings(tmp_path):
    out = make_out(tmp_path)
    (out / "audio" / "002.wav").unlink()
    (out / "line_timings.json").write_text("{not json")
    code, text = run(tmp_path, out)
    assert code == 1
    assert "scene 2" in text and "002.wav" in text and "line_timings.json" not in text


def _snapshot_bytes(out):
    return {p.name: p.read_bytes() for p in out.iterdir() if p.is_file() and not p.is_symlink()}
