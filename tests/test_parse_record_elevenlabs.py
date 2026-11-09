"""parse_record reads ElevenLabs entries (D14): one validator, exact three keys, no clamp."""

import copy
import json
from pathlib import Path

import pytest

from scenevoice.synth.alignment import Alignment
from scenevoice.synth.parse_record import parse_record
from scenevoice.validation import Violation

EXAMPLE = Path(__file__).parent / "fixtures" / "synth_record_contract_example.json"
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


def bad_alignments():
    k = ("characters", "character_start_times_seconds", "character_end_times_seconds")
    yield "null", None
    yield "list", [1]
    yield "string", "x"
    yield "fourth_key", {**ALIGNMENT, "extra": []}
    for key in k:
        yield f"missing_{key}", {x: v for x, v in ALIGNMENT.items() if x != key}
    yield "unequal", {**ALIGNMENT, "characters": ["H"]}
    yield "empty", {key: [] for key in k}
    yield "non_string_char", {**ALIGNMENT, "characters": ["H", 1]}
    for name, t in (("negative", -1), ("bool", True), ("string", "1"), ("huge", 10**400)):
        yield f"time_{name}", {**ALIGNMENT, "character_end_times_seconds": [0.1, t]}


@pytest.mark.parametrize("alignment", [a for _, a in bad_alignments()],
                         ids=[n for n, _ in bad_alignments()])
def test_bad_alignment_is_malformed(alignment):
    assert is_malformed(parse(entry(alignment=alignment)))


def test_language_string_is_malformed():
    assert is_malformed(parse(entry(language="en-GB")))


def test_instruction_string_is_malformed():
    assert is_malformed(parse(entry(instruction="calm")))


def test_gemini_entry_with_alignment_is_malformed():
    assert is_malformed(parse(entry(model="gemini-3.8-flash-tts", language="en-GB")))


def test_elevenlabs_model_not_in_registry_is_malformed():
    assert is_malformed(parse(entry(model="eleven_v3")))
