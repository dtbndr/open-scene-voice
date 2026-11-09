from pathlib import Path

from scenevoice.synth.alignment import Alignment
from scenevoice.synth.record_entry import RecordEntry
from scenevoice.synth.record_name import RECORD_NAME
from scenevoice.synth.serialize_record import serialize_record

FIXTURE = Path(__file__).parent / "fixtures" / "synth_record_contract_example.json"

ALIGNMENT = Alignment(("H", "i", "."), (0.0, 0.08, 0.16), (0.08, 0.16, 0.2))


def _entry(**overrides):
    fields = dict(
        ordinal=1,
        sha256="a" * 64,
        voice="Algenib",
        model="gemini-3.8-flash-tts",
        language="en-GB",
        instruction=None,
        alignment=None,
    )
    fields.update(overrides)
    return RecordEntry(**fields)


def _contract_entries():
    return [
        _entry(),
        _entry(
            ordinal=2,
            sha256="b" * 64,
            voice="EXAVITQu4vr4xnSDxMaL",
            model="eleven_flash_v2_5",
            language=None,
            alignment=ALIGNMENT,
        ),
    ]


def test_record_name():
    assert RECORD_NAME == "synth_record.json"


def test_contract_example_bytes_match_fixture():
    assert serialize_record(_contract_entries()) == FIXTURE.read_bytes()


def test_empty_record_bytes():
    assert serialize_record([]) == b'{\n  "scenes": []\n}\n'


def test_non_ascii_instruction_is_raw_utf8():
    data = serialize_record([_entry(instruction="café ☕")])
    assert "café ☕".encode() in data
    assert b"\\u" not in data


def test_no_bom():
    assert not serialize_record([_entry()]).startswith(b"\xef\xbb\xbf")


def test_ends_with_exactly_one_lf():
    data = serialize_record(_contract_entries())
    assert data.endswith(b"}\n")
    assert not data.endswith(b"\n\n")


def test_null_is_unquoted():
    data = serialize_record([_entry()])
    assert b'"instruction": null' in data
    assert b'"null"' not in data


def test_key_order_independent_of_construction_order():
    entry = RecordEntry(
        alignment=None,
        instruction=None,
        language="en-GB",
        model="m",
        voice="v",
        sha256="s",
        ordinal=3,
    )
    text = serialize_record([entry]).decode("utf-8")
    keys = ["ordinal", "sha256", "voice", "model", "language", "instruction", "alignment"]
    positions = [text.index(f'"{k}"') for k in keys]
    assert positions == sorted(positions)
