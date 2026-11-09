import io

from pack_run_helper import FakeStdin, put_wav, scene, write_plan

from scenevoice.pack import check_no_collision, check_pack_dir, run_pack

MANIFEST = "scene_manifest.csv"


def _run(plan, directory):
    err = io.StringIO()
    code = run_pack(plan, FakeStdin(b""), directory, err)
    return code, err.getvalue()


def test_bad_plan_beats_missing_dir(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_bytes(b"not json")
    missing = tmp_path / "missing"
    assert check_pack_dir(missing) is not None  # the later step is reachable
    code, text = _run(plan, missing)
    assert code == 1
    assert text.startswith("scenevoice pack: FAIL ")
    assert "does not exist" not in text
    assert not missing.exists()


def test_bad_dir_beats_manifest_check(tmp_path):
    # DIR is a file: check 3 would also fail here (lstat under a file raises ENOTDIR).
    plan = write_plan(tmp_path, [scene(1)])
    not_dir = tmp_path / "afile"
    not_dir.write_bytes(b"x")
    assert check_no_collision(not_dir) is not None  # the later step is reachable
    code, text = _run(plan, not_dir)
    assert code == 1
    assert "not a directory" in text
    assert MANIFEST not in text


def test_existing_manifest_beats_missing_wav(tmp_path):
    plan = write_plan(tmp_path, [scene(1)])
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    (out / MANIFEST).write_bytes(b"keep")
    code, text = _run(plan, out)  # no 001.wav: check 4 would also fail
    assert code == 1
    assert MANIFEST in text
    assert "001.wav" not in text
    assert (out / MANIFEST).read_bytes() == b"keep"


def test_missing_wav_beats_later_invalid_wav(tmp_path):
    plan = write_plan(tmp_path, [scene(1), scene(2), scene(3)])
    out = tmp_path / "out"
    out.mkdir()
    put_wav(out, 1)
    (out / "audio" / "003.wav").write_bytes(b"not a wav")  # invalid, but later in plan order
    code, text = _run(plan, out)
    assert code == 1
    assert "audio/002.wav" in text and "audio/003.wav" not in text
    assert not (out / MANIFEST).exists()


def test_invalid_wav_beats_later_missing_wav(tmp_path):
    plan = write_plan(tmp_path, [scene(1), scene(2)])
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    (out / "audio" / "001.wav").write_bytes(b"not a wav")  # first in plan order; 002 is missing
    code, text = _run(plan, out)
    assert code == 1
    assert "audio/001.wav" in text and "audio/002.wav" not in text
    assert not (out / MANIFEST).exists()
