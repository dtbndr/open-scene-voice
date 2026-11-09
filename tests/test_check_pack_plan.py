import io
import json

from scenevoice.pack import check_pack_plan
from scenevoice.synth import PlanScene


def _plan(scenes: list[dict]) -> bytes:
    return json.dumps({"scenes": scenes}).encode("utf-8")


def _scene(i: int, title: str = "T", body: str = "Hello.") -> dict:
    return {"ordinal": i, "title": title, "body": body}


def _write(tmp_path, data: bytes):
    path = tmp_path / "plan.json"
    path.write_bytes(data)
    return path


class _Stdin:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


def _raw_with_title(title_escape: str, count: int = 1) -> bytes:
    scenes = [_scene(i) for i in range(1, count + 1)]
    raw = _plan(scenes).decode("utf-8")
    return raw.replace('"title": "T"', f'"title": "{title_escape}"', 1).encode()


def test_valid_plan_from_path_returns_scenes_in_order(tmp_path):
    path = _write(tmp_path, _plan([_scene(1, "A", "one"), _scene(2, "B", "two")]))
    assert check_pack_plan(path, _Stdin(b"")) == [
        PlanScene(1, "A", "one"),
        PlanScene(2, "B", "two"),
    ]


def test_valid_plan_from_stdin_returns_scenes(tmp_path):
    data = _plan([_scene(1, "A", "one")])
    assert check_pack_plan(None, _Stdin(data)) == [PlanScene(1, "A", "one")]


def test_missing_path_returns_message(tmp_path):
    result = check_pack_plan(tmp_path / "nope.json", _Stdin(b""))
    assert isinstance(result, str) and "cannot read file" in result


def test_directory_as_plan_returns_message(tmp_path):
    result = check_pack_plan(tmp_path, _Stdin(b""))
    assert isinstance(result, str) and "cannot read file" in result


def test_empty_stdin_returns_message():
    result = check_pack_plan(None, _Stdin(b""))
    assert isinstance(result, str) and "stdin is empty" in result


def test_invalid_json_returns_message(tmp_path):
    result = check_pack_plan(_write(tmp_path, b"{nope"), _Stdin(b""))
    assert isinstance(result, str) and "not valid JSON" in result


def test_bad_shape_returns_message(tmp_path):
    result = check_pack_plan(_write(tmp_path, b'{"scenes": []}'), _Stdin(b""))
    assert isinstance(result, str) and "non-empty array" in result


def test_bad_field_returns_message(tmp_path):
    data = _plan([_scene(1, body="  ")])
    result = check_pack_plan(_write(tmp_path, data), _Stdin(b""))
    assert isinstance(result, str) and "scene 1: body is blank" in result


def test_1000_scenes_returns_message_naming_limit(tmp_path):
    data = _plan([_scene(i) for i in range(1, 1001)])
    result = check_pack_plan(_write(tmp_path, data), _Stdin(b""))
    assert isinstance(result, str) and "999" in result and "\n" not in result


def test_999_scenes_pass(tmp_path):
    data = _plan([_scene(i) for i in range(1, 1000)])
    result = check_pack_plan(_write(tmp_path, data), _Stdin(b""))
    assert isinstance(result, list) and len(result) == 999


def test_surrogate_title_returns_message_naming_title(tmp_path):
    result = check_pack_plan(_write(tmp_path, _raw_with_title("\\ud800")), _Stdin(b""))
    assert isinstance(result, str)
    assert "scene 1" in result and "title" in result and "\n" not in result


def test_message_never_echoes_title_text(tmp_path):
    marker = "MARKERxyz"
    raw = _raw_with_title(f"{marker}\\ud800")
    result = check_pack_plan(_write(tmp_path, raw), _Stdin(b""))
    assert isinstance(result, str) and marker not in result


def test_9000_byte_body_passes(tmp_path):
    data = _plan([_scene(1, body="a" * 9000)])
    result = check_pack_plan(_write(tmp_path, data), _Stdin(b""))
    assert isinstance(result, list) and len(result[0].body) == 9000


def test_count_reported_before_surrogate_title(tmp_path):
    raw = _raw_with_title("\\ud800", count=1000)
    result = check_pack_plan(_write(tmp_path, raw), _Stdin(b""))
    assert isinstance(result, str) and "999" in result and "title" not in result


def test_shape_reported_before_surrogate_title(tmp_path):
    raw = b'{"scenes": [{"ordinal": 1, "title": "\\ud800"}]}'
    result = check_pack_plan(_write(tmp_path, raw), _Stdin(b""))
    assert isinstance(result, str) and "exactly ordinal, title and body" in result
