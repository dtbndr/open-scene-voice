import io

from scenevoice.beats import MAX_SCRIPT_CHARS, SCRIPT_TOO_LONG_MESSAGE
from scenevoice.beats.make_beats_say import make_beats_say
from scenevoice.beats.read_beats_script import read_beats_script
from scenevoice.validation.scene import Scene

SCRIPT = "## One\nHello there.\n"


def _write(tmp_path, data: bytes, name="s.md"):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _script_of_chars(n: int) -> str:
    head = "## One\n"
    return head + "a" * (n - len(head))


def test_normal_file_returns_bytes_and_scenes(tmp_path):
    path = _write(tmp_path, SCRIPT.encode())
    result = read_beats_script(path)
    assert not isinstance(result, str)
    data, scenes = result
    assert data == SCRIPT.encode()
    assert len(scenes) == 1 and isinstance(scenes[0], Scene)
    assert scenes[0].title == "One"


def test_missing_file_is_one_line_refusal_naming_path(tmp_path):
    path = tmp_path / "nope.md"
    result = read_beats_script(path)
    assert result == f"could not read the script {path} (No such file or directory)"


def test_exactly_20000_characters_passes(tmp_path):
    text = _script_of_chars(MAX_SCRIPT_CHARS)
    assert len(text) == 20000
    result = read_beats_script(_write(tmp_path, text.encode()))
    assert not isinstance(result, str)


def test_20001_characters_is_too_long(tmp_path):
    text = _script_of_chars(MAX_SCRIPT_CHARS + 1)
    assert read_beats_script(_write(tmp_path, text.encode())) == SCRIPT_TOO_LONG_MESSAGE


def test_80000_bytes_ascii_is_too_long_by_characters(tmp_path):
    data = _script_of_chars(80000).encode()
    assert 79000 < len(data) <= 80000
    assert read_beats_script(_write(tmp_path, data)) == SCRIPT_TOO_LONG_MESSAGE


def test_80001_bytes_is_too_long_without_reading_further(tmp_path):
    # invalid UTF-8 after the bound would give a decode message if it were read
    data = b"a" * 80000 + b"\xff" * 5
    assert read_beats_script(_write(tmp_path, data)) == SCRIPT_TOO_LONG_MESSAGE


def test_bom_is_plan_check_failure_with_line(tmp_path):
    data = b"\xef\xbb\xbf" + SCRIPT.encode()
    assert read_beats_script(_write(tmp_path, data)) == (
        "it does not pass the plan check: The file starts with a hidden marker. "
        "Save it as plain UTF-8 text without a byte order mark. (line 1)"
    )


def test_invalid_utf8_is_plan_check_failure_with_line(tmp_path):
    data = b"## One\nHello.\n\xff\n"
    assert read_beats_script(_write(tmp_path, data)) == (
        "it does not pass the plan check: The file is not plain UTF-8 text. Re-save it as UTF-8. (line 3)"
    )


def test_plan_check_failure_with_line(tmp_path):
    data = b"## One\r\nHello.\n"
    result = read_beats_script(_write(tmp_path, data))
    assert isinstance(result, str)
    assert result.startswith("it does not pass the plan check: ")
    assert result.endswith(")") and "(line " in result


def test_plan_check_failure_without_line(tmp_path):
    result = read_beats_script(_write(tmp_path, b""))
    assert isinstance(result, str)
    assert result.startswith("it does not pass the plan check: ")
    assert "(line" not in result


def test_say_prefixes_and_writes_one_line():
    out = io.StringIO()
    make_beats_say(out, [])("OK x")
    assert out.getvalue() == "scenevoice beats: OK x\n"


def test_say_redacts_every_secret_including_ones_added_later():
    out = io.StringIO()
    secrets: list[str | None] = ["sk-first-secret"]
    say = make_beats_say(out, secrets)
    secrets.append("second-secret")
    say("FAIL /tmp/sk-first-secret.md: bad second-secret here")
    text = out.getvalue()
    assert "sk-first-secret" not in text and "second-secret" not in text
    assert text.startswith("scenevoice beats: FAIL ")

