import io

import pytest
from pack_run_helper import FakeStdin, scene, write_plan
from wav_helper import make_wav

from scenevoice.pack import check_pack_wavs, run_pack
from scenevoice.synth import PlanScene

MANIFEST = "scene_manifest.csv"


def _run(plan, directory):
    err = io.StringIO()
    code = run_pack(plan, FakeStdin(b""), directory, err)
    return code, err.getvalue()


def _audio(out, ordinals=(1, 2), frames=24000):
    (out / "audio").mkdir(parents=True, exist_ok=True)
    for n in ordinals:
        (out / "audio" / f"{n:03d}.wav").write_bytes(make_wav(frames))


def _scenes(n):
    return [PlanScene(i, f"T{i}", "b") for i in range(1, n + 1)]


def test_check4_reads_audio_subdirectory(tmp_path):
    _audio(tmp_path, (1, 2), 10)
    assert check_pack_wavs(_scenes(2), tmp_path) == [10, 10]


def test_check4_ignores_flat_wav_and_stale_audio_file(tmp_path):
    _audio(tmp_path, (1, 2, 7))
    (tmp_path / "003.wav").write_bytes(make_wav())
    assert check_pack_wavs(_scenes(2), tmp_path) == [24000, 24000]


def test_check4_flat_wav_does_not_satisfy_missing_audio_file(tmp_path):
    _audio(tmp_path, (1,))
    (tmp_path / "002.wav").write_bytes(make_wav())
    result = check_pack_wavs(_scenes(2), tmp_path)
    assert isinstance(result, str)
    assert "scene 2" in result and "audio/002.wav" in result


def test_check4_symlinked_wav_in_audio_rejected(tmp_path):
    _audio(tmp_path, (1, 9))
    try:
        (tmp_path / "audio" / "002.wav").symlink_to(tmp_path / "audio" / "009.wav")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    result = check_pack_wavs(_scenes(2), tmp_path)
    assert isinstance(result, str) and "scene 2" in result and "audio/002.wav" in result


@pytest.mark.parametrize("case", ["missing", "file", "symlink", "dangling"])
def test_run_pack_refuses_bad_audio_dir_and_writes_nothing(tmp_path, case):
    plan = write_plan(tmp_path, [scene(1)])
    out = tmp_path / "out"
    out.mkdir()
    if case == "file":
        (out / "audio").write_bytes(b"x")
    elif case in ("symlink", "dangling"):
        if case == "symlink":
            (tmp_path / "real").mkdir()
        try:
            (out / "audio").symlink_to(tmp_path / ("real" if case == "symlink" else "nowhere"))
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported")
    code, text = _run(plan, out)
    assert code == 1
    assert text.startswith("scenevoice pack: FAIL ")
    assert f"{out}/audio" in text
    assert not (out / MANIFEST).exists()
    assert sorted(p.name for p in out.iterdir()) in ([], ["audio"])


def test_run_pack_audio_messages(tmp_path):
    plan = write_plan(tmp_path, [scene(1)])
    out = tmp_path / "out"
    out.mkdir()
    text = _run(plan, out)[1]
    assert text.startswith("scenevoice pack: FAIL ")
    assert f"{out}/audio: directory does not exist" in text
    (out / "audio").write_bytes(b"x")
    assert f"{out}/audio: not a directory" in _run(plan, out)[1]


def test_audio_check_beats_manifest_collision(tmp_path):
    plan = write_plan(tmp_path, [scene(1)])
    out = tmp_path / "out"
    out.mkdir()
    (out / MANIFEST).write_bytes(b"old")
    code, text = _run(plan, out)
    assert code == 1
    assert f"{out}/audio" in text and MANIFEST not in text


def test_audio_check_runs_after_dir_check(tmp_path):
    plan = write_plan(tmp_path, [scene(1)])
    not_dir = tmp_path / "afile"
    not_dir.write_bytes(b"x")
    code, text = _run(plan, not_dir)
    assert code == 1
    assert f"{not_dir}: not a directory" in text
    assert "/audio" not in text


def test_symlinked_dir_with_real_audio_still_packs(tmp_path):
    real = tmp_path / "real"
    _audio(real, (1,))
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    plan = write_plan(tmp_path, [scene(1)])
    code, _ = _run(plan, link)
    assert code == 0
    assert (real / MANIFEST).exists()


def test_manifest_file_column_is_audio_path_with_lf(tmp_path):
    plan = write_plan(tmp_path, [scene(1, "Café, au lait"), scene(2, 'The "big" day')])
    out = tmp_path / "out"
    _audio(out, (1, 2))
    (out / "audio" / "001.wav").write_bytes(make_wav(50400))
    (out / "audio" / "002.wav").write_bytes(make_wav(123456))
    code, _ = _run(plan, out)
    assert code == 0
    assert (out / MANIFEST).read_bytes() == (
        b"scene,label,file,duration_s\n"
        b'1,"Caf\xc3\xa9, au lait",audio/001.wav,2.100\n'
        b'2,"The ""big"" day",audio/002.wav,5.144\n'
    )
    assert sorted(p.name for p in out.iterdir()) == ["audio", MANIFEST]
