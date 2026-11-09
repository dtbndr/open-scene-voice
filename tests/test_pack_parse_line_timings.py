import json
from pathlib import Path

import pytest

from scenevoice.pack import LineTiming, parse_line_timings

H = "a" * 64
GOLDEN = Path(__file__).parent / "fixtures" / "line_timings_worked_example.json"


def doc(*entries):
    return json.dumps({"scenes": list(entries)}).encode()


def entry(**over):
    base = {"ordinal": 1, "sha256": H, "lines": [{"text": "Hi.", "start_ms": 0}]}
    base.update(over)
    return base


def assert_rejected(data):
    result = parse_line_timings(data)
    assert isinstance(result, str)
    assert "line_timings.json" in result
    assert "\n" not in result


def test_golden_worked_example_is_accepted():
    table = parse_line_timings(GOLDEN.read_bytes())
    assert isinstance(table, dict)
    assert sorted(table) == [1, 2]
    assert table[1][0] == "1" * 64
    assert table[1][1] == [
        LineTiming("Hello there.", 0),
        LineTiming("Nothing matched here.", None),
        LineTiming("Last line.", 4120),
    ]
    assert table[2][1][0] == LineTiming('She said "café" twice.', 240)


def test_unindented_contract_example_is_accepted():
    data = (
        '{"scenes":[{"ordinal":1,"sha256":"' + H + '","lines":'
        '[{"text":"A.","start_ms":null}]}]}'
    ).encode()
    assert parse_line_timings(data) == {1: (H, [LineTiming("A.", None)])}


@pytest.mark.parametrize(
    "data",
    [
        b"[]",
        b'"x"',
        b"{}",
        b'{"scenes": {}}',
        b'{"scenes": null}',
        doc(5),
        doc(entry(lines=[5])),
        doc(entry(ordinal=True)),
        doc(entry(ordinal=1.0)),
        doc(entry(ordinal=1.5)),
        doc(entry(ordinal="1")),
        doc({"sha256": H, "lines": []}),
        doc(entry(sha256="a" * 63)),
        doc(entry(sha256="a" * 65)),
        doc(entry(sha256="A" * 64)),
        doc(entry(sha256="g" * 64)),
        doc(entry(sha256=None)),
        doc({"ordinal": 1, "sha256": H}),
        doc(entry(lines={})),
        doc(entry(lines=[{"start_ms": 0}])),
        doc(entry(lines=[{"text": 5, "start_ms": 0}])),
        b'{"scenes":[{"ordinal":1,"sha256":"%s","lines":[{"text":"\\ud800","start_ms":0}]}]}'
        % H.encode(),
        doc(entry(lines=[{"text": "x", "start_ms": True}])),
        doc(entry(lines=[{"text": "x", "start_ms": 1.0}])),
        doc(entry(lines=[{"text": "x", "start_ms": 1.5}])),
        doc(entry(lines=[{"text": "x", "start_ms": -1}])),
        doc(entry(lines=[{"text": "x", "start_ms": "1"}])),
        doc(entry(lines=[{"text": "x"}])),
        doc(entry(), entry()),
        doc(entry(ordinal=7, sha256="bad")),
        b"\xef\xbb\xbf" + doc(),
        doc() + b" x",
        b'{"scenes": [], "scenes": []}',
        b'{"scenes": [{"ordinal": NaN}]}',
        b"\xff\xfe",
        b"",
    ],
)
def test_malformed_is_rejected_with_a_named_one_line_message(data):
    assert_rejected(data)


def test_entry_not_in_plan_that_is_malformed_is_still_malformed():
    assert_rejected(doc(entry(), entry(ordinal=999, sha256="short")))


def test_well_formed_entry_for_any_ordinal_is_kept_for_the_caller_to_ignore():
    table = parse_line_timings(doc(entry(ordinal=999)))
    assert isinstance(table, dict) and 999 in table


def test_null_start_is_accepted():
    table = parse_line_timings(doc(entry(lines=[{"text": "x", "start_ms": None}])))
    assert table == {1: (H, [LineTiming("x", None)])}


def test_unknown_fields_are_ignored_at_every_level():
    data = doc(
        entry(extra=1, lines=[{"text": "x", "start_ms": 3, "more": [1]}])
    )
    data = data.replace(b'{"scenes"', b'{"version": 2, "scenes"')
    assert parse_line_timings(data) == {1: (H, [LineTiming("x", 3)])}


def test_empty_scenes_and_empty_lines_are_allowed():
    assert parse_line_timings(doc()) == {}
    assert parse_line_timings(doc(entry(lines=[]))) == {1: (H, [])}


def test_zero_start_and_large_start_are_accepted():
    table = parse_line_timings(
        doc(entry(lines=[{"text": "a", "start_ms": 0}, {"text": "b", "start_ms": 10**9}]))
    )
    assert isinstance(table, dict)
    assert [line.start_ms for line in table[1][1]] == [0, 10**9]
