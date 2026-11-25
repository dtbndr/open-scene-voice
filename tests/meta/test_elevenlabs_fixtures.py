import base64
import json

from paths_helper import FIXTURES

DIR = FIXTURES / "elevenlabs"
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


def test_each_negative_variant_differs_from_success_in_the_named_key_only():
    """P0 guard: a negative fixture must isolate one fault, or the synth rows built on it prove nothing."""
    base = _load("success_flash.json")
    for name, key in sorted(KEY_FOR.items()):
        doc = _load(name)
        differing = {k for k in base.keys() | doc.keys() if k not in doc or k not in base or doc[k] != base[k]}
        # NaN != NaN keeps nan_time in the differing set, which is the expected key anyway.
        assert differing == {key}, name
