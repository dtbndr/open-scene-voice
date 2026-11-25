import hashlib
import os
import sys
from dataclasses import replace

import pytest
from web_http_helper import HOST, make_request

from scenevoice.align.scene_timings import SceneTimings
from scenevoice.align.serialize_timings import serialize_timings
from scenevoice.align.split_sentences import split_sentences
from scenevoice.align.white_space import WHITE_SPACE_CHARS as ALIGN_CHARS
from scenevoice.align.white_space import WHITE_SPACE_RUN as ALIGN_RUN
from scenevoice.pack import LineTiming
from scenevoice.web import (
    MISMATCH,
    NOTHING_VOICED,
    WHITE_SPACE_CHARS,
    WHITE_SPACE_RUN,
    AudioScan,
    PlannedScene,
    RecordItem,
    RecordRead,
    TimingsRead,
    check_duplicates,
    check_rest_ready,
    collapse_text,
    hash_wav,
    read_line_timings,
    scan_audio,
    scan_backups,
    text_witness,
)

KEY = b"key"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir()
    return audio


def test_a_plain_wav_is_voiced_with_the_sha256_of_its_bytes(tmp_path):
    audio = make(tmp_path)
    (audio / "001.wav").write_bytes(b"one")
    (audio / "0002.wav").write_bytes(b"two")
    assert scan_audio(tmp_path, None) == AudioScan((1, 2), {1: sha(b"one"), 2: sha(b"two")})


def test_no_audio_folder_or_a_symlinked_one_is_nothing_voiced(tmp_path):
    assert scan_audio(tmp_path, None) == AudioScan()
    real = tmp_path / "elsewhere"
    real.mkdir()
    (real / "001.wav").write_bytes(b"x")
    os.symlink(real, tmp_path / "audio")
    assert scan_audio(tmp_path, None) == AudioScan()


def test_a_symlink_a_hard_linked_file_a_directory_and_the_key_file_are_named_but_not_voiced(tmp_path):
    audio = make(tmp_path)
    (tmp_path / "outside").write_bytes(b"o")
    os.symlink(tmp_path / "outside", audio / "001.wav")
    (audio / "002.wav").write_bytes(b"t")
    os.link(audio / "002.wav", audio / "twin")
    (audio / "003.wav").mkdir()
    (audio / "004.wav").write_bytes(KEY)
    (audio / "005.wav").write_bytes(b"ok")
    got = scan_audio(tmp_path, audio / "004.wav")
    assert got == AudioScan((1, 2, 3, 4, 5), {5: sha(b"ok")})


def test_other_names_are_neither_named_nor_voiced_and_are_never_read(tmp_path, monkeypatch):
    audio = make(tmp_path)
    for name in (".write-ab12.tmp", "001.wav.bak", "1.wav", "01.wav", "0000001.wav", "001.WAV", "notes.txt", "001.wav "):
        (audio / name).write_bytes(b"x")
    (audio / "002.wav").write_bytes(b"2")
    module = sys.modules["scenevoice.web.scan_audio"]
    opened = []
    real = module.hash_wav
    monkeypatch.setattr(module, "hash_wav", lambda path, *args: opened.append(path.name) or real(path, *args))
    assert scan_audio(tmp_path, None) == AudioScan((2,), {2: sha(b"2")})
    assert opened == ["002.wav"]  # positive control and: only an allowlisted name is opened


def test_a_wav_is_hashed_in_one_mib_chunks_and_a_file_over_the_cap_is_not_voiced(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.web.hash_wav"]
    sizes = []
    real = module.os.read
    monkeypatch.setattr(module.os, "read", lambda fd, n: sizes.append(n) or real(fd, n))
    path = tmp_path / "a.wav"
    data = b"x" * (2 * 1024 * 1024 + 5)
    path.write_bytes(data)
    assert hash_wav(path, None) == sha(data)
    assert sizes == [1024 * 1024, 1024 * 1024, 5]
    assert hash_wav(path, None, cap=len(data)) == sha(data)
    assert hash_wav(path, None, cap=len(data) - 1) is None
    assert hash_wav(tmp_path / "missing.wav", None) is None


def test_the_folder_fact_is_true_only_for_a_real_audio_directory(tmp_path):
    assert scan_audio(tmp_path, None).folder is False
    (tmp_path / "audio").write_bytes(b"a file")
    assert scan_audio(tmp_path, None).folder is False
    (tmp_path / "audio").unlink()
    real = tmp_path / "elsewhere"
    real.mkdir()
    os.symlink(real, tmp_path / "audio")
    assert scan_audio(tmp_path, None).folder is False
    (tmp_path / "audio").unlink()
    (tmp_path / "audio").mkdir()
    assert scan_audio(tmp_path, None).folder is True


@pytest.mark.parametrize(
    ("where", "name"),
    [(".", ".write-restart-0a1b-001.wav.tmp"), ("audio", ".write-restart-deadbeef01-synth_record.json.tmp")],
)
def test_an_exact_restart_backup_that_is_a_regular_file_is_found_in_the_project_folder_or_audio(tmp_path, where, name):
    (tmp_path / "audio").mkdir()
    (tmp_path / where / name).write_bytes(b"x")
    assert scan_backups(tmp_path) is True


@pytest.mark.parametrize(
    "name",
    [
        ".write-restore-0a1b-001.wav.tmp",
    ],
)
def test_other_names_are_not_backups(tmp_path, name):
    (tmp_path / "audio").mkdir()
    (tmp_path / name).write_bytes(b"x")
    (tmp_path / "audio" / name).write_bytes(b"x")
    assert scan_backups(tmp_path) is False


def test_a_symlink_or_a_directory_with_a_backup_name_is_not_a_backup_and_nothing_is_opened(tmp_path):
    (tmp_path / "audio").mkdir()
    name = ".write-restart-0a1b-001.wav.tmp"
    os.symlink(tmp_path / "audio", tmp_path / name)
    (tmp_path / "audio" / name).mkdir()
    assert scan_backups(tmp_path) is False


def test_a_symlinked_audio_folder_is_not_listed_and_no_folder_is_false(tmp_path):
    assert scan_backups(tmp_path) is False
    real = tmp_path / "elsewhere"
    real.mkdir()
    (real / ".write-restart-0a1b-001.wav.tmp").write_bytes(b"x")
    os.symlink(real, tmp_path / "audio")
    assert scan_backups(tmp_path) is False


SCENES = (PlannedScene(1, "A", "One one."), PlannedScene(2, "B", "Two two."), PlannedScene(3, "C", "Three three."))
H = {n: chr(96 + n) * 64 for n in range(1, 10)}


def entry(n, **changes):
    base = RecordItem(n, H[n], "Leda", "gemini-3.8-flash-tts", "en-GB", None, None)
    return replace(base, **changes)


def audio(*ordinals, hashes=None):
    return AudioScan(tuple(ordinals), hashes if hashes is not None else {n: H[n] for n in ordinals})


def record(*items):
    return RecordRead("ok", tuple(items))


NO_TIMINGS = TimingsRead("none")


def check(audio_scan, record_read, timings=NO_TIMINGS):
    return check_rest_ready(SCENES, audio_scan, record_read, timings)


def test_the_passing_case_is_a_partly_voiced_script_with_one_record_and_no_false_witness():
    assert check(audio(1, 2), record(entry(1), entry(2))) is None
    assert check(audio(1, 2, 3), record(entry(1), entry(2), entry(3))) is None


def test_an_entry_for_a_scene_that_is_not_voiced_yet_is_allowed_if_it_agrees():
    assert check(audio(1), record(entry(1), entry(2))) is None


@pytest.mark.parametrize(
    "audio_scan",
    [
        pytest.param(AudioScan(), id="no-audio-folder-or-no-wav"),
    ],
)
def test_nothing_voiced_is_refused_so_the_creator_uses_all(audio_scan):
    assert check(audio_scan, record(entry(1))) == NOTHING_VOICED


@pytest.mark.parametrize(
    ("audio_scan", "record_read", "timings"),
    [
        pytest.param(audio(1), RecordRead("none"), NO_TIMINGS, id="no-record"),
        pytest.param(audio(1, 2), record(entry(1)), NO_TIMINGS, id="voiced-scene-without-an-entry"),
        pytest.param(audio(1, 2), record(entry(1), entry(2, voice="Zephyr")), NO_TIMINGS, id="entries-disagree-on-voice"),
        pytest.param(audio(1, 2), record(entry(1), entry(2, model="other")), NO_TIMINGS, id="entries-disagree-on-model"),
        pytest.param(audio(1, 2), record(entry(1), entry(2, language=None)), NO_TIMINGS, id="entries-disagree-on-language"),
        pytest.param(audio(1, 2, hashes={1: H[1], 2: "x" * 64}), record(entry(1), entry(2)), NO_TIMINGS, id="record-sha-differs-from-the-wav"),
        pytest.param(audio(1), record(entry(1, characters="Other text.")), NO_TIMINGS, id="alignment-does-not-join-to-the-body"),
    ],
)
def test_every_other_refusal_gives_the_one_mismatch_message(audio_scan, record_read, timings):
    assert check(audio_scan, record_read, timings) == MISMATCH


def test_a_witness_that_is_true_or_absent_does_not_refuse():
    assert check(audio(1), record(entry(1, characters="One one."))) is None  # alignment joins to the body
    assert check(audio(1), record(entry(1)), TimingsRead("ok", {1: (H[1], "One one.")})) is None  # fresh timings agree
    assert check(audio(1), record(entry(1)), TimingsRead("ok", {1: ("0" * 64, "Stale text.")})) is None  # stale: no witness
    assert check(audio(1), record(entry(1)), TimingsRead("unreadable")) is None


def test_the_texts_of_the_messages_are_the_approved_wording():
    assert NOTHING_VOICED == "Nothing has been voiced yet."
    assert MISMATCH == "What was voiced does not match this script or these settings. Choose Start again."


@pytest.mark.parametrize("name", ["host", "origin", "content-type", "content-length"])
def test_any_duplicate_guarded_header_is_a_bad_request(name: str) -> None:
    request = make_request(headers=[("host", HOST), (name, "a"), (name, "a")] if name != "host" else [("host", HOST), ("host", HOST)])
    refusal = check_duplicates(request)
    assert refusal is not None
    assert refusal.status == 400
    assert refusal.body.startswith(b'{"error": {"kind": "bad_request"')


def test_single_guarded_headers_and_duplicates_of_other_headers_pass() -> None:
    request = make_request(
        headers=[("host", HOST), ("origin", "o"), ("content-type", "t"), ("content-length", "1"), ("accept", "a"), ("accept", "b")]
    )
    assert check_duplicates(request) is None


BODIES = [
    "Hello there.",
    "One.\r\nTwo.\r\n\r\nThree",
    "Non\xa0breaking space. Next\u2028line\u3000here.",
    "  leading and   inner\tspaces\x85and\u200atrailing  ",
    "Dr. Smith went home!  Then? Yes.",
    "",
    "\x1cnot white space\x1f",
]


def test_the_white_space_set_is_the_align_set():
    assert WHITE_SPACE_CHARS == ALIGN_CHARS
    assert WHITE_SPACE_RUN.pattern == ALIGN_RUN.pattern


@pytest.mark.parametrize("body", BODIES)
def test_the_collapsed_body_is_what_the_stored_sentence_texts_join_to(body, tmp_path):
    sentences = split_sentences(body)
    assert " ".join(sentences) == collapse_text(body)
    sha = "c" * 64
    scene = SceneTimings(1, sha, [LineTiming(text, 10 * i) for i, text in enumerate(sentences)])
    (tmp_path / "line_timings.json").write_bytes(serialize_timings([scene]))
    table = read_line_timings(tmp_path, None)
    assert table.state == "ok"
    assert text_witness(PlannedScene(1, "T", body), None, sha, table) is True
