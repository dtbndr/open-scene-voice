import copy
import json
import os
import re
import sys
from typing import Any

import pytest
from beats.test_sidecar_shape import good
from record_helper import eleven_entry, gemini_entry, sha_of, write_record

from scenevoice.beats import check_sidecar_shape
from scenevoice.web import (
    RecordItem,
    RecordRead,
    TimingsRead,
    beats_candidate,
    beats_light_check,
    classify_line_markers,
    common_settings,
    read_beats_state,
    read_line_timings,
    read_record,
)

WAV = b"wav"


def item(ordinal=1, **fields):
    base = {
        "ordinal": ordinal, "sha256": "a" * 64, "voice": "Leda", "model": "gemini-3.8-flash-tts",
        "language": "en-GB", "instruction": None, "characters": None,
    }
    return RecordItem(**{**base, **fields})


def test_no_record_is_none(tmp_path):
    assert read_record(tmp_path, None) == RecordRead("none")


def test_a_gemini_and_an_elevenlabs_entry_become_items_in_file_order(tmp_path):
    write_record(tmp_path, gemini_entry(1, WAV), eleven_entry(3, WAV, "Hi there"))
    got = read_record(tmp_path, None)
    assert got.state == "ok"
    assert [(i.ordinal, i.model, i.language, i.instruction, i.characters) for i in got.items] == [
        (1, "gemini-3.8-flash-tts", "en-GB", None, None),
        (3, "eleven_flash_v2_5", None, None, "Hi there"),
    ]
    assert got.items[0].sha256 == sha_of(WAV) and got.items[0].voice == "Leda"


def test_an_empty_scene_list_is_an_ok_record_with_no_items(tmp_path):
    (tmp_path / "synth_record.json").write_text('{"scenes": []}')
    assert read_record(tmp_path, None) == RecordRead("ok", ())


def altered(**changes):
    entry = gemini_entry(1, WAV)
    entry.update(changes)
    return entry


@pytest.mark.parametrize(
    "document",
    [
        pytest.param([], id="not-an-object"),
        pytest.param({"scenes": {}}, id="scenes-not-a-list"),
        pytest.param({"scenes": [{k: v for k, v in gemini_entry(1, WAV).items() if k != "voice"}]}, id="missing-key"),
        pytest.param({"scenes": [gemini_entry(2, WAV), gemini_entry(2, WAV)]}, id="repeated-ordinal"),
    ],
)
def test_a_record_of_the_wrong_shape_is_unreadable(tmp_path, document):
    (tmp_path / "synth_record.json").write_text(json.dumps(document))
    assert read_record(tmp_path, None) == RecordRead("unreadable")


def test_the_record_is_read_through_the_bounded_json_reader_with_a_32_mib_cap(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.web.read_record"]
    asked = []
    real = module.read_json_file
    monkeypatch.setattr(module, "read_json_file", lambda *args: asked.append(args[1:]) or real(*args))
    (tmp_path / "synth_record.json").write_text("{")
    assert read_record(tmp_path, None).state == "unreadable"  # malformed: the reader's answer is passed on
    assert asked == [("synth_record.json", 32 * 1024 * 1024, None)]  # positive control: the spy saw the call


def test_the_common_settings_are_the_shared_values_or_none_when_entries_disagree_or_are_absent():
    assert common_settings(()) is None
    assert common_settings((item(1), item(2))) == {
        "voice": "Leda", "model": "gemini-3.8-flash-tts", "language": "en-GB", "instruction": None,
    }
    for changes in ({"voice": "Zephyr"}, {"model": "other"}, {"language": None}, {"instruction": "slow"}):
        assert common_settings((item(1), item(2, **changes))) is None


SHA1, SHA2, SHA3 = "1" * 64, "2" * 64, "3" * 64


def write(directory, scenes):
    (directory / "line_timings.json").write_text(json.dumps({"scenes": scenes}, ensure_ascii=False), encoding="utf-8")


def scene(ordinal, sha, texts=("One.", "Two.")):
    return {"ordinal": ordinal, "sha256": sha, "lines": [{"text": text, "start_ms": 10 * i} for i, text in enumerate(texts)]}


def test_no_file_is_none(tmp_path):
    assert read_line_timings(tmp_path, None) == TimingsRead("none")


def test_entries_map_an_ordinal_to_its_sha_and_the_line_texts_joined_with_one_space(tmp_path):
    write(tmp_path, [scene(1, SHA1), scene(2, SHA2, ("Sol\xe9.",))])
    assert read_line_timings(tmp_path, None) == TimingsRead("ok", {1: (SHA1, "One. Two."), 2: (SHA2, "Sol\xe9.")})


@pytest.mark.parametrize(
    "document",
    [
        pytest.param([], id="not-an-object"),
        pytest.param({"scenes": [scene(1, "x")]}, id="bad-sha"),
        pytest.param({"scenes": [scene(1, SHA1), scene(1, SHA2)]}, id="repeated-ordinal"),
    ],
)
def test_a_file_of_the_wrong_shape_is_unreadable(tmp_path, document):
    (tmp_path / "line_timings.json").write_text(json.dumps(document))
    assert read_line_timings(tmp_path, None) == TimingsRead("unreadable")


def fresh_table():
    return TimingsRead("ok", {1: (SHA1, "a"), 2: (SHA2, "b"), 3: (SHA3, "c")})


@pytest.mark.parametrize(
    ("ordinals", "timings", "hashes", "expected"),
    [
        pytest.param((1,), TimingsRead("unreadable"), {1: SHA1}, ("unreadable", ()), id="unreadable"),
        pytest.param((1, 2, 3), fresh_table(), {1: SHA1, 2: SHA2, 3: SHA3}, ("fresh", ()), id="every-scene-matches"),
        pytest.param((1, 2, 3), fresh_table(), {1: SHA1, 2: "9" * 64, 3: SHA3}, ("stale", (2,)), id="one-scene-stale"),
        pytest.param((1, 2, 3), TimingsRead("ok", {1: (SHA1, "a"), 3: (SHA3, "c")}), {1: SHA1, 2: SHA2, 3: SHA3}, ("stale", (2,)), id="missing-entry"),
    ],
)
def test_line_markers_are_fresh_only_when_every_plan_scene_entry_matches_its_wav(ordinals, timings, hashes, expected):
    assert classify_line_markers(ordinals, timings, hashes) == expected


SHA = "ab" * 32
OTHER = "cd" * 32


def sidecar(sha=SHA, **changes):
    return {**{"version": 1, "script_sha256": sha, "scenes": []}, **changes}


def write_read_beats_state(directory, document):
    (directory / "beats.json").write_text(json.dumps(document), encoding="utf-8")


def test_no_beats_file_is_none(tmp_path):
    assert read_beats_state(tmp_path, SHA, None) == "none"


def test_a_sidecar_for_these_script_bytes_is_fresh_and_for_other_bytes_or_no_script_is_stale(tmp_path):
    write_read_beats_state(tmp_path, sidecar())
    assert read_beats_state(tmp_path, SHA, None) == "fresh"
    assert read_beats_state(tmp_path, OTHER, None) == "stale"
    assert read_beats_state(tmp_path, None, None) == "stale"


@pytest.mark.parametrize(
    "document",
    [
        pytest.param([], id="not-an-object"),
        pytest.param(sidecar(version=2), id="other-version"),
        pytest.param(sidecar(sha="ab" * 31), id="short-sha"),
    ],
)
def test_the_light_check_refuses_a_sidecar_of_the_wrong_shape_and_the_state_is_invalid(tmp_path, document):
    assert beats_light_check(document) is None
    write_read_beats_state(tmp_path, document)
    assert read_beats_state(tmp_path, SHA, None) == "invalid"


def test_the_light_check_returns_the_script_hash_of_a_good_sidecar():
    assert beats_light_check(sidecar()) == SHA


def test_a_malformed_or_symlinked_file_is_invalid(tmp_path):
    (tmp_path / "beats.json").write_text("{")
    assert read_beats_state(tmp_path, SHA, None) == "invalid"
    (tmp_path / "beats.json").unlink()
    (tmp_path / "real.json").write_text(json.dumps(sidecar()))
    os.symlink(tmp_path / "real.json", tmp_path / "beats.json")
    assert read_beats_state(tmp_path, SHA, None) == "invalid"


def without(key: str) -> dict[str, Any]:
    doc = copy.deepcopy(good())
    del doc[key]
    return doc


def with_(**changes: Any) -> dict[str, Any]:
    return {**copy.deepcopy(good()), **changes}


TOP_LEVEL = {
    "valid": good(),
    "no-scenes": without("scenes"),
    "no-hash": without("script_sha256"),
    "extra-key": with_(extra=1),
    "version-2": with_(version=2),
    "hash-upper": with_(script_sha256="A" * 64),
}


@pytest.mark.parametrize("name", TOP_LEVEL)
def test_the_light_check_and_the_cli_check_agree_on_the_top_level_shape(name):
    document = TOP_LEVEL[name]
    assert (beats_light_check(document) is not None) == (check_sidecar_shape(copy.deepcopy(document)) is None)


@pytest.mark.parametrize("document", [[], "text", 1, None, True])
def test_neither_check_accepts_a_document_that_is_not_an_object(document):
    assert beats_light_check(document) is None and check_sidecar_shape(document) is not None


def test_the_light_check_leaves_the_deeper_scene_checks_to_the_cli():
    deeper = with_(scenes=[{"nonsense": True}])
    assert beats_light_check(deeper) is not None and check_sidecar_shape(deeper) is not None


NAME = re.compile(r"\.write-beats-[0-9a-f]{16,}\.tmp")


def test_the_candidate_is_a_new_name_in_the_project_folder_that_does_not_exist_yet(tmp_path):
    path = beats_candidate(tmp_path)
    assert path.parent == tmp_path and NAME.fullmatch(path.name) and not os.path.lexists(path)
    assert os.listdir(tmp_path) == []


def test_two_candidates_differ(tmp_path):
    assert beats_candidate(tmp_path) != beats_candidate(tmp_path)


def test_a_name_that_exists_already_is_skipped_even_as_a_dangling_symlink(tmp_path, monkeypatch):
    names = iter(["aa" * 8, "aa" * 8, "bb" * 8])
    monkeypatch.setattr(sys.modules["scenevoice.web.beats_candidate"].secrets, "token_hex", lambda size: next(names))
    (tmp_path / f".write-beats-{'aa' * 8}.tmp").symlink_to(tmp_path / "nowhere")
    assert beats_candidate(tmp_path).name == f".write-beats-{'bb' * 8}.tmp"
