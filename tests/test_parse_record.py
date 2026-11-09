import json

import pytest

from scenevoice.synth import RecordEntry, parse_record, serialize_record
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


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"\xff\xfe{}", id="not-utf8"),
        pytest.param(b"\xef\xbb\xbf" + serialize_record(()), id="bom"),
        pytest.param(b"", id="empty"),
        pytest.param(b"   \n", id="whitespace-only"),
        pytest.param(serialize_record(()) + serialize_record(()), id="two-documents"),
        pytest.param(serialize_record(()) + b"x", id="trailing-data"),
        pytest.param(b'{"scenes": [], "scenes": []}', id="duplicate-top-key"),
        pytest.param(
            b'{"scenes": [{"ordinal": 1, "ordinal": 1, "sha256": "' + b"a" * 64
            + b'", "voice": "V", "model": "gemini-3.8-flash-tts", "language": null,'
            b' "instruction": null, "alignment": null}]}',
            id="duplicate-entry-key",
        ),
        pytest.param(b'{"scenes": [NaN]}', id="nan"),
        pytest.param(b'{"scenes": [Infinity]}', id="infinity"),
        pytest.param(b'{"scenes": [-Infinity]}', id="negative-infinity"),
        pytest.param(b"[]", id="top-level-array"),
        pytest.param(b'{"scenes": [], "extra": 1}', id="extra-top-key"),
        pytest.param(b"{}", id="missing-scenes"),
        pytest.param(b'{"scenes": {}}', id="scenes-object"),
        pytest.param(b'{"scenes": null}', id="scenes-null"),
        pytest.param(b'{"scenes": [null]}', id="scenes-contains-null"),
        pytest.param(b'{"scenes": [[]]}', id="entry-array"),
        pytest.param(b'{"scenes": ["x"]}', id="entry-string"),
    ],
)
def test_document_level_malformed(data):
    _assert_malformed(data)


@pytest.mark.parametrize(
    "key", ["ordinal", "sha256", "voice", "model", "language", "instruction", "alignment"]
)
def test_entry_missing_a_key_is_malformed(key):
    _assert_malformed(_without_key(key))


def test_entry_with_eighth_key_is_malformed():
    _assert_malformed(_with_entry(seed=1))


@pytest.mark.parametrize("ordinal", [0, -1, True, False, 1.0, "1", None, [], {}])
def test_bad_ordinal(ordinal):
    _assert_malformed(_with_entry(ordinal=ordinal))


def test_ordinal_one_e_zero_is_malformed():
    data = _with_entry(ordinal=0).replace(b'"ordinal": 0', b'"ordinal": 1e0')
    assert b"1e0" in data
    _assert_malformed(data)


def test_duplicate_ordinals_are_malformed():
    doc = _valid_doc()
    doc["scenes"][1]["ordinal"] = 1
    _assert_malformed(_dump(doc))


def test_descending_ordinals_are_malformed():
    doc = _valid_doc()
    doc["scenes"][0]["ordinal"] = 2
    doc["scenes"][1]["ordinal"] = 1
    _assert_malformed(_dump(doc))


@pytest.mark.parametrize(
    "sha",
    [
        "a" * 63,
        "a" * 65,
        "A" + "a" * 63,
        "g" + "a" * 63,
        "a" * 64 + "\n",
        "",
        1,
        None,
        ["a"],
    ],
)
def test_bad_sha256(sha):
    _assert_malformed(_with_entry(sha256=sha))


@pytest.mark.parametrize("voice", ["", "  ", "\t\n", None, 1, [], False])
def test_bad_voice(voice):
    _assert_malformed(_with_entry(voice=voice))


@pytest.mark.parametrize(
    "model",
    [
        "",
        "  ",
        None,
        1,
        "eleven_v4",
        "eleven_flash_v2_5",
        "gemini-3.1-flash-tts",
        "unknown",
    ],
)
def test_bad_model(model):
    _assert_malformed(_with_entry(model=model))


@pytest.mark.parametrize("language", [1, [], False, {}])
def test_bad_language(language):
    _assert_malformed(_with_entry(language=language))


@pytest.mark.parametrize("instruction", [False, 1, [], {}])
def test_bad_instruction(instruction):
    _assert_malformed(_with_entry(instruction=instruction))


@pytest.mark.parametrize(
    "alignment",
    [
        {},
        [],
        "x",
        0,
        {
            "characters": ["H"],
            "character_start_times_seconds": [0.0],
            "character_end_times_seconds": [0.1],
        },
    ],
)
def test_bad_alignment_on_gemini_entry(alignment):
    _assert_malformed(_with_entry(alignment=alignment))


def test_null_language_on_gemini_entry_is_valid():
    result = parse_record(_with_entry(language=None))
    assert isinstance(result, tuple)
    assert result[0].language is None


def test_literal_none_instruction_is_valid():
    result = parse_record(_with_entry(instruction="(none)"))
    assert isinstance(result, tuple)
    assert result[0].instruction == "(none)"


def test_non_ascii_voice_is_valid():
    result = parse_record(_with_entry(voice="Léda"))
    assert isinstance(result, tuple)
    assert result[0].voice == "Léda"


def test_huge_ordinal_is_valid():
    doc = _valid_doc()
    doc["scenes"][1]["ordinal"] = 10**9
    result = parse_record(_dump(doc))
    assert isinstance(result, tuple)
    assert result[1].ordinal == 10**9


def test_ordinal_gaps_are_valid():
    doc = _valid_doc()
    doc["scenes"][1]["ordinal"] = 3
    result = parse_record(_dump(doc))
    assert isinstance(result, tuple)
    assert [e.ordinal for e in result] == [1, 3]


def test_syntax_error_violation_has_no_line():
    result = parse_record(b'{"scenes": [')
    assert isinstance(result, Violation)
    assert result.line is None

