
import pytest
from paths_helper import FIXTURES

from scenevoice.align import SceneTimings, serialize_timings
from scenevoice.pack import LineTiming, parse_line_timings

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


def test_cafe_golden_bytes() -> None:
    expected = (FIXTURES / "line_timings_cafe.json").read_bytes()
    assert serialize_timings(_cafe_scenes()) == expected


def test_worked_example_golden_bytes() -> None:
    expected = (FIXTURES / "line_timings_worked_example.json").read_bytes()
    assert serialize_timings(_worked_scenes()) == expected


# Control-character classes: NUL, named escape (tab, newline), last C0 code.
@pytest.mark.parametrize("code", [0, 9, 10, 31])
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


def test_empty_lines_and_empty_scenes() -> None:
    scene = SceneTimings(ordinal=3, sha256=HASH_A, lines=[])
    assert b'"lines": []\n' in serialize_timings([scene])
    assert serialize_timings([]) == b'{\n  "scenes": []\n}\n'


def test_serializer_output_parses_to_the_same_lines():
    scenes = [
        SceneTimings(1, "0" * 64, [LineTiming("Hello.", 0), LineTiming("Miss.", None)]),
        SceneTimings(2, "f" * 64, [LineTiming('Café "quoted"   \U0001f600', 1234)]),
        SceneTimings(3, "0" * 64, []),
    ]
    table = parse_line_timings(serialize_timings(scenes))
    assert table == {s.ordinal: (s.sha256, s.lines) for s in scenes}
    assert parse_line_timings(serialize_timings([])) == {}
