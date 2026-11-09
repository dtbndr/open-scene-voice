import base64
import binascii
import json
from pathlib import Path

import pytest

DIR = Path(__file__).parent / "fixtures" / "elevenlabs"
EXCLUDED = {"non_json.txt", "non_utf8.bin", "top_level_array.json", "utf16_json.bin"}

# Fixture name -> the one top-level key it differs in from success_flash.json.
KEY_FOR = {
    "missing_audio.json": "audio_base64",
    "non_string_audio.json": "audio_base64",
    "bad_base64.json": "audio_base64",
    "empty_pcm.json": "audio_base64",
    "odd_pcm.json": "audio_base64",
    "missing_alignment.json": "alignment",
    "null_alignment.json": "alignment",
    "alignment_not_object.json": "alignment",
    "missing_array.json": "alignment",
    "array_not_list.json": "alignment",
    "unequal_arrays.json": "alignment",
    "empty_arrays.json": "alignment",
    "non_string_character.json": "alignment",
    "negative_time.json": "alignment",
    "boolean_time.json": "alignment",
    "string_time.json": "alignment",
    "nan_time.json": "alignment",
    "huge_time.json": "alignment",
    "huge_int_time.json": "alignment",
    "normalized_ignored.json": "normalized_alignment",
    "lone_surrogate_character.json": "alignment",
}


def _load(name):
    return json.loads((DIR / name).read_bytes().decode("utf-8"))


def _pcm_or_none(path):
    try:
        doc = json.loads(path.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("audio_base64"), str):
        return None
    try:
        return base64.b64decode(doc["audio_base64"], validate=True)
    except binascii.Error:
        return None


def test_success_flash_facts():
    doc = _load("success_flash.json")
    assert len(base64.b64decode(doc["audio_base64"], validate=True)) == 9600
    assert doc["alignment"] == {
        "characters": ["I", "t"],
        "character_start_times_seconds": [0.0, 0.128],
        "character_end_times_seconds": [0.128, 0.186],
    }
    assert all(len(v) == 2 for v in doc["alignment"].values())


def test_success_v4_overshoot_facts():
    doc = _load("success_v4_overshoot.json")
    assert len(base64.b64decode(doc["audio_base64"], validate=True)) == 7200
    assert doc["alignment"]["character_end_times_seconds"][-1] == 0.24


def test_no_fixture_pcm_is_longer_than_one_second():
    checked = 0
    for path in sorted(DIR.iterdir()):
        pcm = _pcm_or_none(path)
        if pcm is not None:
            checked += 1
            assert len(pcm) <= 48000, path.name
    assert checked >= 20


@pytest.mark.parametrize("name", sorted(KEY_FOR))
def test_variant_differs_from_success_in_the_named_key_only(name):
    base, doc = _load("success_flash.json"), _load(name)
    differing = {k for k in base.keys() | doc.keys() if k not in doc or k not in base or doc[k] != base[k]}
    # NaN != NaN keeps nan_time in the differing set, which is the expected key anyway.
    assert differing == {KEY_FOR[name]}


def test_every_fixture_is_covered_by_a_fact():
    names = {p.name for p in DIR.iterdir()}
    assert names == set(KEY_FOR) | EXCLUDED | {"success_flash.json", "success_v4_overshoot.json"}


def test_utf16_fixture_is_not_utf8_and_small():
    raw = (DIR / "utf16_json.bin").read_bytes()
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")
    assert len(raw) < 1024


@pytest.mark.parametrize("path", sorted(DIR.iterdir()), ids=lambda p: p.name)
def test_fixture_is_at_most_20_kb(path):
    assert path.stat().st_size <= 20 * 1024
