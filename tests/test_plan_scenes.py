from pathlib import Path

import pytest

from scenevoice.cli.main import main


def _run(data, tmp_path, capsys):
    script = tmp_path / "script.md"
    script.write_bytes(data)
    code = main(["plan", str(script)])
    captured = capsys.readouterr()
    return script, code, captured


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"# Title\n\n[Pronunciations]\nAurelius = Oh-REE-lee-us\n", id="preamble-only"),
    ],
)
def test_plan_rejects_missing_marker_without_line(data, tmp_path, capsys):
    script, code, captured = _run(data, tmp_path, capsys)
    assert code == 1
    assert captured.err.startswith(f"scenevoice plan: FAIL {script}:")
    assert "(line" not in captured.err
    assert captured.err.endswith("\n")
    assert captured.out == ""


@pytest.mark.parametrize(
    "data, line",
    [
        pytest.param(b"## \nbody\n", 1, id="blank-title"),
        pytest.param(b"# T\n\n## A\n   \n\n", 3, id="whitespace-body"),
        pytest.param(b"## A\n\xc2\xa0\n", 1, id="nbsp-body"),
        pytest.param(b"## A\n\xe3\x80\x80\n", 1, id="ideographic-space-body"),
        pytest.param(b"## A\n## B\ntext\n", 1, id="adjacent-markers"),
        pytest.param(b"## A\ntext\n## B\n", 3, id="final-marker-lf-eof"),
        pytest.param(b"## A\ntext\n## B", 3, id="final-marker-eof"),
        pytest.param("## A\ntext\u2028more\n## B\n".encode(), 3, id="u2028-not-a-line-break"),
    ],
)
def test_plan_rejects_scene_violation_with_line(data, line, tmp_path, capsys):
    script, code, captured = _run(data, tmp_path, capsys)
    assert code == 1
    assert captured.err.startswith(f"scenevoice plan: FAIL {script}:")
    assert captured.err.endswith(f"(line {line})\n")
    assert captured.out == ""


@pytest.mark.parametrize(
    "data, line",
    [
        pytest.param(b"## A\r\n\r\n", 1, id="crlf-with-blank-body"),
        pytest.param(b"\xef\xbb\xbf## A\ntext\n", 1, id="bom-with-valid-scene"),
        pytest.param(b"\xef\xbb\xbftext only\n", 1, id="bom-with-no-marker"),
    ],
)
def test_plan_lexical_rules_still_win(data, line, tmp_path, capsys):
    script, code, captured = _run(data, tmp_path, capsys)
    assert code == 1
    assert captured.err.startswith(f"scenevoice plan: FAIL {script}:")
    assert captured.err.endswith(f"(line {line})\n")
    assert captured.out == ""


@pytest.mark.parametrize(
    "data, fragment",
    [
        pytest.param(b"## A\r\n\r\n", "carriage return", id="cr"),
        pytest.param(b"\xef\xbb\xbf## A\ntext\n", "byte order mark", id="bom"),
    ],
)
def test_plan_lexical_message_names_the_rule(data, fragment, tmp_path, capsys):
    _, _, captured = _run(data, tmp_path, capsys)
    assert fragment in captured.err


CONTRACT_EXAMPLES = (
    b"# Video\n\n[Pronunciations]\nAurelius = Oh-REE-lee-us\n\n"
    b"## Arrival\nOne [pause] two.\n\n"
    b"##   Arrival\nwhisper this\n\n"
    b"## Arrival\nsay this slowly\n\n"
    b"### not a marker\n"
)


def test_plan_accepts_contract_examples(tmp_path, capsys):
    script, code, captured = _run(CONTRACT_EXAMPLES, tmp_path, capsys)
    assert code == 0
    assert captured.err == f"scenevoice plan: OK {script}\n"


@pytest.mark.parametrize("name", ["sample/scripts/short.md", "sample/scripts/long.md"])
def test_plan_accepts_sample_scripts_with_scenes(name, capsys):
    path = Path(__file__).resolve().parent.parent / name
    assert main(["plan", str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.err == f"scenevoice plan: OK {path}\n"
