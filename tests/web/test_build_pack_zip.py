import errno
import io
import os
import zipfile

import pytest

from scenevoice.web import build_pack_zip
from scenevoice.web.workspace_error import NothingPackedError, PackTooLargeError

MANIFEST = b"scene,file\n1,audio/001.wav\n"
OTIO = b'{"OTIO_SCHEMA": "Timeline.1"}'
WAV_1 = b"RIFF-one"
WAV_2 = b"RIFF-two"


@pytest.fixture
def project(tmp_path):
    directory = tmp_path.resolve() / "ws" / "my-video"
    (directory / "audio").mkdir(parents=True)
    (directory / "scene_manifest.csv").write_bytes(MANIFEST)
    (directory / "resolve_timeline.otio").write_bytes(OTIO)
    (directory / "audio" / "002.wav").write_bytes(WAV_2)
    (directory / "audio" / "001.wav").write_bytes(WAV_1)
    return directory


def read_zip(data):
    archive = zipfile.ZipFile(io.BytesIO(data))
    return archive, {info.filename: archive.read(info) for info in archive.infolist()}


def names(project, **options):
    archive, _ = read_zip(build_pack_zip(project, "my-video", options.pop("key_file", None), **options))
    return [info.filename for info in archive.infolist()]


def test_the_zip_holds_the_allowlisted_files_under_the_id_folder_sorted_stored_and_byte_for_byte(project):
    archive, contents = read_zip(build_pack_zip(project, "my-video", None))
    assert [info.filename for info in archive.infolist()] == [
        "my-video/audio/001.wav",
        "my-video/audio/002.wav",
        "my-video/resolve_timeline.otio",
        "my-video/scene_manifest.csv",
    ]
    assert {info.compress_type for info in archive.infolist()} == {zipfile.ZIP_STORED}
    assert contents == {
        "my-video/audio/001.wav": WAV_1,
        "my-video/audio/002.wav": WAV_2,
        "my-video/resolve_timeline.otio": OTIO,
        "my-video/scene_manifest.csv": MANIFEST,
    }


def test_the_same_files_give_the_same_bytes_and_a_pre_1980_mtime_is_clamped(project):
    for path in project.rglob("*"):
        if path.is_file():
            os.utime(path, (0, 0))
    first = build_pack_zip(project, "my-video", None)
    assert build_pack_zip(project, "my-video", None) == first
    archive, _ = read_zip(first)
    assert {info.date_time for info in archive.infolist()} == {(1980, 1, 1, 0, 0, 0)}


def test_nothing_outside_the_allowlist_is_zipped_even_when_it_is_present(project):
    for name in ("script.md", "synth_record.json", "line_timings.json", "beats.json", ".write-ab12.tmp", "notes.txt"):
        (project / name).write_bytes(b"leak")
    for name in ("readme.txt", "001.WAV", "1.wav", "0001.wav.bak", ".write-ab12.tmp", "x001.wav"):
        (project / "audio" / name).write_bytes(b"leak")
    (project / "audio" / "nested").mkdir()
    (project / "audio" / "nested" / "003.wav").write_bytes(b"leak")
    (project / "elsewhere").mkdir()
    (project / "elsewhere" / "004.wav").write_bytes(b"leak")
    assert names(project) == [
        "my-video/audio/001.wav",
        "my-video/audio/002.wav",
        "my-video/resolve_timeline.otio",
        "my-video/scene_manifest.csv",
    ]


def test_a_missing_timeline_is_fine_and_a_missing_audio_folder_is_fine(project):
    (project / "resolve_timeline.otio").unlink()
    assert names(project) == ["my-video/audio/001.wav", "my-video/audio/002.wav", "my-video/scene_manifest.csv"]
    for path in (project / "audio").iterdir():
        path.unlink()
    (project / "audio").rmdir()
    assert names(project) == ["my-video/scene_manifest.csv"]


def test_a_missing_manifest_is_nothing_packed_even_with_wavs_and_a_timeline(project):
    (project / "scene_manifest.csv").unlink()
    with pytest.raises(NothingPackedError):
        build_pack_zip(project, "my-video", None)


def test_a_differently_spelled_entry_contributes_nothing(project):
    (project / "resolve_timeline.otio").rename(project / "Resolve_Timeline.otio")
    (project / "audio" / "001.wav").rename(project / "audio" / "001.WAV")
    (project / "audio").rename(project / "Audio")
    (project / "Audio" / "002.wav").rename(project / "Audio" / "tmp.wav")
    (project / "scene_manifest.csv").rename(project / "Scene_Manifest.csv")
    with pytest.raises(NothingPackedError):
        build_pack_zip(project, "my-video", None)


def test_a_symlinked_file_or_audio_folder_contributes_nothing(project, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.wav").write_bytes(b"leak")
    (project / "audio" / "003.wav").symlink_to(outside / "secret.wav")
    (project / "resolve_timeline.otio").unlink()
    (project / "resolve_timeline.otio").symlink_to(outside / "secret.wav")
    assert names(project) == ["my-video/audio/001.wav", "my-video/audio/002.wav", "my-video/scene_manifest.csv"]
    (outside / "003.wav").write_bytes(b"leak")
    for path in (project / "audio").iterdir():
        path.unlink()
    (project / "audio").rmdir()
    (project / "audio").symlink_to(outside)
    assert names(project) == ["my-video/scene_manifest.csv"]
    (project / "scene_manifest.csv").unlink()
    (project / "scene_manifest.csv").symlink_to(outside / "secret.wav")
    with pytest.raises(NothingPackedError):
        build_pack_zip(project, "my-video", None)


def test_a_file_with_a_second_hard_link_contributes_nothing_and_its_bytes_are_not_in_the_zip(project, tmp_path):
    os.link(project / "audio" / "002.wav", tmp_path / "other-name")
    os.link(project / "resolve_timeline.otio", tmp_path / "other-timeline")
    data = build_pack_zip(project, "my-video", None)
    assert [info.filename for info in read_zip(data)[0].infolist()] == ["my-video/audio/001.wav", "my-video/scene_manifest.csv"]
    assert WAV_2 not in data and OTIO not in data
    os.link(project / "scene_manifest.csv", tmp_path / "other-manifest")
    with pytest.raises(NothingPackedError):
        build_pack_zip(project, "my-video", None)


def test_the_key_file_is_left_out_of_the_zip_and_a_key_file_manifest_is_nothing_packed(project):
    secret = b"GOOGLE_KEY=hunter2"
    (project / "audio" / "002.wav").write_bytes(secret)
    data = build_pack_zip(project, "my-video", project / "audio" / "002.wav")
    assert [info.filename for info in read_zip(data)[0].infolist()] == [
        "my-video/audio/001.wav",
        "my-video/resolve_timeline.otio",
        "my-video/scene_manifest.csv",
    ]
    assert b"hunter2" not in data
    assert b"hunter2" in build_pack_zip(project, "my-video", None)  # positive control: zipped without the closure
    (project / "scene_manifest.csv").write_bytes(secret)
    with pytest.raises(NothingPackedError):
        build_pack_zip(project, "my-video", project / "scene_manifest.csv")


def test_a_total_over_the_cap_is_refused_before_anything_is_read_and_the_cap_itself_is_allowed(project, monkeypatch):
    total = len(MANIFEST) + len(OTIO) + len(WAV_1) + len(WAV_2)
    assert len(build_pack_zip(project, "my-video", None, cap=total)) > total
    reads = []
    real_read = os.read
    monkeypatch.setattr(os, "read", lambda fd, count: reads.append(count) or real_read(fd, count))
    with pytest.raises(PackTooLargeError):
        build_pack_zip(project, "my-video", None, cap=total - 1)
    assert reads == []


@pytest.fixture
def descriptors(monkeypatch, project):
    """Tracks descriptors opened under the project; `limit` raises EMFILE once that many are open at once."""
    state = {"open": set(), "peak": 0, "limit": None}
    real_open, real_close = os.open, os.close

    def tracked_open(path, flags, *args, **kwargs):
        mine = str(path).startswith(str(project))
        if mine and state["limit"] is not None and len(state["open"]) >= state["limit"]:
            raise OSError(errno.EMFILE, "Too many open files")
        fd = real_open(path, flags, *args, **kwargs)
        if mine:
            state["open"].add(fd)
            state["peak"] = max(state["peak"], len(state["open"]))
        return fd

    def tracked_close(fd):
        state["open"].discard(fd)
        real_close(fd)

    monkeypatch.setattr(os, "open", tracked_open)
    monkeypatch.setattr(os, "close", tracked_close)
    return state


def test_hundreds_of_wavs_survive_a_small_open_file_limit_because_one_descriptor_is_open_at_a_time(project, descriptors):
    for number in range(3, 60):
        (project / "audio" / f"{number:03d}.wav").write_bytes(b"wav%d" % number)
    descriptors["limit"] = 4
    got = names(project)
    assert len([name for name in got if name.endswith(".wav")]) == 59
    assert descriptors["peak"] == 1 and descriptors["open"] == set()
    descriptors["limit"] = 0  # positive control: the limit does bite when nothing may be open
    with pytest.raises(NothingPackedError):
        build_pack_zip(project, "my-video", None)


def test_every_descriptor_is_closed_after_a_zip_a_refusal_and_a_failed_read(project, descriptors, monkeypatch):
    build_pack_zip(project, "my-video", None)
    assert descriptors["peak"] == 1 and descriptors["open"] == set()
    with pytest.raises(PackTooLargeError):
        build_pack_zip(project, "my-video", None, cap=3)
    assert descriptors["open"] == set()
    real_read = os.read

    def failing_read(fd, count):
        if os.fstat(fd).st_size == len(WAV_2):
            raise OSError(errno.EIO, "disk error")
        return real_read(fd, count)

    monkeypatch.setattr(os, "read", failing_read)
    assert "my-video/audio/002.wav" not in names(project)  # left out, and the zip is still built
    assert descriptors["open"] == set()
