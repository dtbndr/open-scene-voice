import json
from pathlib import Path

import pytest

from scenevoice.cli.main import main
from scenevoice.validation.load_scenes import load_scenes

ROOT = Path(__file__).resolve().parent.parent


def _run(data, tmp_path, capsysbinary):
    script = tmp_path / "script.md"
    script.write_bytes(data)
    code = main(["plan", str(script)])
    return code, capsysbinary.readouterr()


def _scenes(captured):
    return json.loads(captured.out.decode("utf-8"))["scenes"]


@pytest.mark.parametrize("name", ["sample/scripts/short.md", "sample/scripts/long.md"])
def test_stdout_scenes_match_the_scene_parser(name, capsysbinary):
    path = ROOT / name
    expected = load_scenes(path.read_bytes())
    assert main(["plan", str(path)]) == 0
    scenes = _scenes(capsysbinary.readouterr())
    assert [(s["ordinal"], s["title"], s["body"]) for s in scenes] == [
        (s.ordinal, s.title, s.body) for s in expected
    ]


def test_stdout_scene_keys_are_exactly_ordinal_title_body(capsysbinary):
    assert main(["plan", str(ROOT / "sample/scripts/short.md")]) == 0
    for scene in _scenes(capsysbinary.readouterr()):
        assert set(scene) == {"ordinal", "title", "body"}


CONTRACT_EXAMPLES = (
    b"# Video\n\n[Pronunciations]\nAurelius = Oh-REE-lee-us\n\n"
    b"## Arrival\nOne [pause] two.\n\n"
    b"##   Arrival\nwhisper this\n\n"
    b"## Arrival\nsay this slowly\n\n"
    b"### not a marker\n"
)


def test_contract_examples_produce_the_expected_scenes(tmp_path, capsysbinary):
    code, captured = _run(CONTRACT_EXAMPLES, tmp_path, capsysbinary)
    assert code == 0
    assert _scenes(captured) == [
        {"ordinal": 1, "title": "Arrival", "body": "One [pause] two.\n\n"},
        {"ordinal": 2, "title": "  Arrival", "body": "whisper this\n\n"},
        {"ordinal": 3, "title": "Arrival", "body": "say this slowly\n\n### not a marker\n"},
    ]


def test_ordinals_come_from_position_not_from_the_title(tmp_path, capsysbinary):
    titles = ["Scene 1: a", "Scene 2: b", "Scene 3: c", "Scene 4: d", "Scene 6: e"]
    data = "".join(f"## {t}\ntext\n" for t in titles).encode("utf-8")
    code, captured = _run(data, tmp_path, capsysbinary)
    assert code == 0
    scenes = _scenes(captured)
    assert [s["ordinal"] for s in scenes] == [1, 2, 3, 4, 5]
    assert scenes[4]["title"] == "Scene 6: e"


def test_non_ascii_appears_as_written_on_raw_stdout(tmp_path, capsysbinary):
    title = "Caf\u00e9 \u65e5\u672c"
    body = "na\u00efve\u2028line \u200b zero \U0001f600\n"
    data = f"## {title}\n{body}".encode()
    code, captured = _run(data, tmp_path, capsysbinary)
    assert code == 0
    raw = captured.out.decode("utf-8")
    assert title in raw
    assert "na\u00efve\u2028line \u200b zero \U0001f600" in raw
    assert "\\u" not in raw
    assert _scenes(captured) == [{"ordinal": 1, "title": title, "body": body}]


def test_body_whitespace_is_not_stripped(tmp_path, capsysbinary):
    code, captured = _run(b"## A \n\n  text  \n\n", tmp_path, capsysbinary)
    assert code == 0
    assert _scenes(captured) == [{"ordinal": 1, "title": "A ", "body": "\n  text  \n\n"}]


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"## A\n\xff\xfe\n", id="invalid-utf8"),
        pytest.param(b"\xef\xbb\xbf## A\ntext\n", id="bom"),
        pytest.param(b"## A\r\ntext\r\n", id="cr"),
        pytest.param(b"## A\ntext\x07\n", id="disallowed-control"),
        pytest.param(b"# Title\n\nno markers here\n", id="no-marker"),
        pytest.param(b"## \ntext\n", id="blank-title"),
        pytest.param(b"## A\n## B\ntext\n", id="empty-body"),
        pytest.param(b"## A\n \t\n\xc2\xa0\xe3\x80\x80\n", id="white-space-only-body"),
    ],
)
def test_rejected_scripts_write_nothing_to_stdout(data, tmp_path, capsysbinary):
    code, captured = _run(data, tmp_path, capsysbinary)
    assert code == 1
    assert captured.out == b""
    assert captured.err.startswith(b"scenevoice plan: FAIL ")
