"""parse_record reads ElevenLabs entries (D14): one validator, exact three keys, no clamp."""

import copy
import json

import paths_helper
import pytest

from scenevoice.synth import (
    RECORD_NAME,
    RecordEntry,
    load_record,
    parse_record,
    serialize_record,
)
from scenevoice.synth.alignment import Alignment
from scenevoice.validation import Violation

MALFORMED = (
    "synth_record.json is not a valid synth record "
    "(delete it to regenerate without a settings check)"
)


GEMINI = "gemini-3.8-flash-tts"


def _entry(ordinal=1, **overrides):
    fields = dict(
        ordinal=ordinal,
        sha256="a" * 64,
        voice="Algenib",
        model=GEMINI,
        language="en-GB",
        instruction=None,
        alignment=None,
    )
    fields.update(overrides)
    return RecordEntry(**fields)


def _valid_doc():
    return json.loads(serialize_record((_entry(1), _entry(2, sha256="b" * 64))))


def _dump(doc):
    return json.dumps(doc).encode("utf-8")


def _with_entry(**changes):
    doc = _valid_doc()
    doc["scenes"][0].update(changes)
    return _dump(doc)


def _without_key(key):
    doc = _valid_doc()
    del doc["scenes"][0][key]
    return _dump(doc)


def _assert_malformed(data):
    result = parse_record(data)
    assert isinstance(result, Violation)
    assert result.message == MALFORMED
    assert result.line is None


def test_empty_record_parses_to_empty_tuple():
    assert parse_record(serialize_record(())) == ()


def test_valid_record_parses_in_file_order():
    entries = (_entry(1), _entry(2, sha256="b" * 64, instruction="calm"))
    assert parse_record(serialize_record(entries)) == entries


def test_hand_written_record_with_other_whitespace_and_key_order():
    data = (
        b'\t{ "scenes":[{"alignment":null,"instruction":null,"language":"en-US",'
        b'"model":"gemini-3.8-flash-tts","voice":"Leda","sha256":"'
        + b"c" * 64
        + b'","ordinal":3}] }\r\n'
    )
    assert parse_record(data) == (
        _entry(3, sha256="c" * 64, voice="Leda", language="en-US"),
    )


def test_returned_entries_are_a_tuple():
    assert isinstance(parse_record(serialize_record((_entry(),))), tuple)


# P1 (settings-match guard): a malformed synth_record.json is refused before a
# regen can mix settings; one row or two per malformed class.
@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"\xff\xfe{}", id="not-utf8"),
        pytest.param(serialize_record(()) + b"x", id="trailing-data"),
        pytest.param(b'{"scenes": [NaN]}', id="nan"),
        pytest.param(b"[]", id="top-level-array"),
        pytest.param(b'{"scenes": [], "extra": 1}', id="extra-top-key"),
        pytest.param(b'{"scenes": ["x"]}', id="entry-string"),
    ],
)
def test_document_level_malformed(data):
    _assert_malformed(data)


def test_entry_missing_a_key_is_malformed():
    _assert_malformed(_without_key("sha256"))


def test_entry_with_eighth_key_is_malformed():
    _assert_malformed(_with_entry(seed=1))


@pytest.mark.parametrize("ordinal", [0, True, "1"])
def test_bad_ordinal(ordinal):
    _assert_malformed(_with_entry(ordinal=ordinal))


def test_duplicate_or_descending_ordinals_are_malformed():
    doc = _valid_doc()
    doc["scenes"][1]["ordinal"] = 1
    _assert_malformed(_dump(doc))
    doc["scenes"][0]["ordinal"] = 2
    _assert_malformed(_dump(doc))


@pytest.mark.parametrize("sha", ["a" * 63, "A" + "a" * 63, None])
def test_bad_sha256(sha):
    _assert_malformed(_with_entry(sha256=sha))


@pytest.mark.parametrize("voice", ["", None])
def test_bad_voice(voice):
    _assert_malformed(_with_entry(voice=voice))


@pytest.mark.parametrize("model", ["", "unknown"])
def test_bad_model(model):
    _assert_malformed(_with_entry(model=model))


def test_bad_language_and_instruction_types():
    _assert_malformed(_with_entry(language=1))
    _assert_malformed(_with_entry(instruction=False))


def test_null_language_and_literal_none_instruction_are_valid():
    result = parse_record(_with_entry(language=None, instruction="(none)"))
    assert isinstance(result, tuple)
    assert (result[0].language, result[0].instruction) == (None, "(none)")


def test_ordinal_gaps_are_valid():
    doc = _valid_doc()
    doc["scenes"][1]["ordinal"] = 3
    result = parse_record(_dump(doc))
    assert isinstance(result, tuple)
    assert [e.ordinal for e in result] == [1, 3]


EXAMPLE = paths_helper.FIXTURES / "synth_record_contract_example.json"


SHA = "b" * 64


ALIGNMENT = {
    "characters": ["H", "i"],
    "character_start_times_seconds": [0.0, 0.08],
    "character_end_times_seconds": [0.08, 0.16],
}


def entry(**changes):
    base = {
        "ordinal": 1, "sha256": SHA, "voice": "EXAVITQu4vr4xnSDxMaL",
        "model": "eleven_flash_v2_5", "language": None, "instruction": None,
        "alignment": copy.deepcopy(ALIGNMENT),
    }
    base.update(changes)
    return base


def parse(item):
    return parse_record(json.dumps({"scenes": [item]}).encode())


def is_malformed(result):
    return isinstance(result, Violation) and result.line is None and (
        result.message == "synth_record.json is not a valid synth record "
        "(delete it to regenerate without a settings check)")


def test_valid_entry_carries_alignment_as_tuples_of_floats():
    result = parse(entry())
    assert not isinstance(result, Violation)
    assert result[0].alignment == Alignment(("H", "i"), (0.0, 0.08), (0.08, 0.16))
    assert result[0].language is None and result[0].instruction is None


def test_contract_example_parses_to_gemini_and_elevenlabs_entries():
    result = parse_record(EXAMPLE.read_bytes())
    assert not isinstance(result, Violation)
    assert [e.model for e in result] == ["gemini-3.8-flash-tts", "eleven_flash_v2_5"]
    assert result[0].alignment is None and result[1].alignment is not None


def test_integer_time_is_accepted_as_float():
    a = {**ALIGNMENT, "character_start_times_seconds": [0, 1]}
    result = parse(entry(alignment=a))
    assert result[0].alignment.character_start_times_seconds == (0.0, 1.0)
    assert all(type(t) is float for t in result[0].alignment.character_start_times_seconds)


def test_times_beyond_any_duration_are_not_clamped():
    a = {**ALIGNMENT, "character_end_times_seconds": [1e6, 2e6]}
    assert parse(entry(alignment=a))[0].alignment.character_end_times_seconds == (1e6, 2e6)


@pytest.mark.parametrize(
    "alignment",
    [
        None,
        {**ALIGNMENT, "extra": []},
        {x: v for x, v in ALIGNMENT.items() if x != "characters"},
        {**ALIGNMENT, "characters": ["H"]},
        {**ALIGNMENT, "character_end_times_seconds": [0.1, -1]},
    ],
    ids=["null", "fourth_key", "missing_key", "unequal", "negative_time"],
)
def test_bad_alignment_is_malformed(alignment):
    assert is_malformed(parse(entry(alignment=alignment)))


def test_language_string_is_malformed():
    assert is_malformed(parse(entry(language="en-GB")))


def test_gemini_entry_with_alignment_is_malformed():
    assert is_malformed(parse(entry(model="gemini-3.8-flash-tts", language="en-GB")))


def test_elevenlabs_model_not_in_registry_is_malformed():
    assert is_malformed(parse(entry(model="eleven_v3")))


def _loaded_entry():
    return RecordEntry(1, "a" * 64, "Algenib", "gemini-3.8-flash-tts", "en-GB", None, None)


def test_absent_file_returns_none(tmp_path):
    assert load_record(tmp_path) is None


def test_valid_file_returns_entries(tmp_path):
    (tmp_path / RECORD_NAME).write_bytes(serialize_record((_loaded_entry(),)))
    assert load_record(tmp_path) == (_loaded_entry(),)


def test_malformed_file_returns_violation(tmp_path):
    (tmp_path / RECORD_NAME).write_bytes(b"{")
    result = load_record(tmp_path)
    assert isinstance(result, Violation)
    assert result.message == MALFORMED
    assert result.line is None
