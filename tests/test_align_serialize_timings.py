import dataclasses
import json
from pathlib import Path

import pytest

from scenevoice.align import SceneTimings, serialize_timings
from scenevoice.pack import LineTiming

FIXTURES = Path(__file__).parent / "fixtures"
HASH_A = "a" * 64


def _cafe_scenes() -> list[SceneTimings]:
    return [
        SceneTimings(
            ordinal=2,
            sha256=HASH_A,
            lines=[
                LineTiming(text='She said "café" twice.', start_ms=240),
                LineTiming(text="Next one.", start_ms=None),
            ],
        )
    ]


def _worked_scenes() -> list[SceneTimings]:
    return [
        SceneTimings(
            ordinal=1,
            sha256="1" * 64,
            lines=[
                LineTiming(text="Hello there.", start_ms=0),
                LineTiming(text="Nothing matched here.", start_ms=None),
                LineTiming(text="Last line.", start_ms=4120),
            ],
        ),
        SceneTimings(
            ordinal=2,
            sha256="2" * 64,
            lines=[
                LineTiming(text='She said "café" twice.', start_ms=240),
                LineTiming(text="Next one.", start_ms=None),
            ],
        ),
    ]


def _one_line(text: str, start_ms: int | None = 0) -> bytes:
    scene = SceneTimings(
        ordinal=1, sha256=HASH_A, lines=[LineTiming(text=text, start_ms=start_ms)]
    )
    return serialize_timings([scene])


def test_fixture_shape_pin() -> None:
    for name in ("line_timings_cafe.json", "line_timings_worked_example.json"):
        raw = (FIXTURES / name).read_bytes()
        doc = json.loads(raw.decode("utf-8"))
        assert list(doc) == ["scenes"]
        for scene in doc["scenes"]:
            assert list(scene) == ["ordinal", "sha256", "lines"]
            assert len(scene["sha256"]) == 64
            for line in scene["lines"]:
                assert list(line) == ["text", "start_ms"]
    worked = json.loads((FIXTURES / "line_timings_worked_example.json").read_bytes())
    assert [s["sha256"] for s in worked["scenes"]] == ["1" * 64, "2" * 64]
    assert any(
        line["start_ms"] is None for s in worked["scenes"] for line in s["lines"]
    )


def test_cafe_golden_bytes() -> None:
    expected = (FIXTURES / "line_timings_cafe.json").read_bytes()
    assert serialize_timings(_cafe_scenes()) == expected


def test_worked_example_golden_bytes() -> None:
    expected = (FIXTURES / "line_timings_worked_example.json").read_bytes()
    assert serialize_timings(_worked_scenes()) == expected


def test_returns_bytes() -> None:
    assert isinstance(serialize_timings(_cafe_scenes()), bytes)


def test_exactly_one_final_lf_no_bom_no_cr() -> None:
    out = serialize_timings(_worked_scenes())
    assert out.endswith(b"}\n")
    assert not out.endswith(b"\n\n")
    assert not out.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in out


def test_e_acute_is_c3_a9_not_escaped() -> None:
    out = _one_line("café")
    assert b"caf\xc3\xa9" in out
    assert b"\\u00e9" not in out


def test_two_space_indent_bare_comma_and_colon_space() -> None:
    out = serialize_timings(_worked_scenes()).decode("utf-8")
    assert '\n  "scenes": [\n    {\n      "ordinal": 1,\n' in out
    assert ", " not in out.replace("Hello there.", "").replace("said", "")


@pytest.mark.parametrize("code", list(range(0x20)))
def test_control_characters(code: int) -> None:
    out = _one_line(chr(code)).decode("utf-8")
    named = {8: "\\b", 9: "\\t", 10: "\\n", 12: "\\f", 13: "\\r"}
    expected = named.get(code, f"\\u{code:04x}")
    assert f'"text": "{expected}"' in out
    assert chr(code) not in out.replace("\n", "") or code == 10


def test_lowercase_hex_in_control_escape() -> None:
    out = _one_line("\x1f").decode("utf-8")
    assert "\\u001f" in out
    assert "\\u001F" not in out


def test_quote_and_backslash_escaped() -> None:
    out = _one_line('a"b\\c').decode("utf-8")
    assert '"a\\"b\\\\c"' in out


def test_slash_del_and_line_separators_raw() -> None:
    out = _one_line("a/b\x7fc d e")
    assert "a/b\x7fc d e".encode() in out
    assert b"\\/" not in out
    assert b"\\u007f" not in out
    assert b"\\u2028" not in out
    assert b"\\u2029" not in out


def test_null_start_written_as_null_without_comma() -> None:
    out = _one_line("x", None).decode("utf-8")
    assert '"start_ms": null\n' in out


def test_integer_start_has_no_decimal_point() -> None:
    assert b'"start_ms": 240\n' in _one_line("x", 240)


def test_key_order() -> None:
    out = serialize_timings(_cafe_scenes()).decode("utf-8")
    keys = ["scenes", "ordinal", "sha256", "lines", "text", "start_ms"]
    positions = [out.index(f'"{k}"') for k in keys]
    assert positions == sorted(positions)


def test_empty_lines_and_empty_scenes() -> None:
    scene = SceneTimings(ordinal=3, sha256=HASH_A, lines=[])
    assert b'"lines": []\n' in serialize_timings([scene])
    assert serialize_timings([]) == b'{\n  "scenes": []\n}\n'


def test_deterministic() -> None:
    assert serialize_timings(_worked_scenes()) == serialize_timings(_worked_scenes())


def test_output_decodes_to_the_input_structure() -> None:
    doc = json.loads(serialize_timings(_worked_scenes()).decode("utf-8"))
    assert doc["scenes"][0]["lines"][1] == {
        "text": "Nothing matched here.",
        "start_ms": None,
    }
    assert doc["scenes"][1]["ordinal"] == 2


def test_line_timing_is_frozen_and_exported_from_pack() -> None:
    line = LineTiming(text="x", start_ms=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        line.start_ms = 2  # type: ignore[misc]
    assert LineTiming.__module__ == "scenevoice.pack.line_timing"
