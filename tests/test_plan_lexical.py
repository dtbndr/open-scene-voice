from pathlib import Path

import pytest

from scenevoice.cli.main import main


@pytest.mark.parametrize(
    "data, line",
    [
        (b"\xef\xbb\xbfhello\n", 1),
        (b"a\nb\nc\xff\n", 3),
    ],
)
def test_plan_rejects_undecodable_file(data, line, tmp_path, capsys):
    script = tmp_path / "script.md"
    script.write_bytes(data)
    assert main(["plan", str(script)]) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith(f"scenevoice plan: FAIL {script}:")
    assert captured.err.endswith(f"(line {line})\n")
    assert captured.out == ""


@pytest.mark.parametrize(
    "data, line",
    [
        (b"a\r\nb\r\n", 1),
        (b"a\nb\nc\rd\n", 3),
        (b"a\n\tb\n", 2),
        (b"a\x00b\n", 1),
        (b"a\n\xc2\x85b\n", 2),
        (b"a\r\n\tb\n", 1),
    ],
)
def test_plan_rejects_cr_and_control_characters(data, line, tmp_path, capsys):
    script = tmp_path / "script.md"
    script.write_bytes(data)
    assert main(["plan", str(script)]) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith(f"scenevoice plan: FAIL {script}:")
    assert captured.err.endswith(f"(line {line})\n")
    assert captured.out == ""


@pytest.mark.parametrize("name", ["sample/scripts/short.md", "sample/scripts/long.md"])
def test_plan_accepts_sample_scripts(name, capsys):
    path = Path(__file__).resolve().parent.parent / name
    assert main(["plan", str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.err == f"scenevoice plan: OK {path}\n"
