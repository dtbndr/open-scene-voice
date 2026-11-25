import json

from paths_helper import FIXTURES as ALL_FIXTURES

FIXTURES = ALL_FIXTURES / "openrouter"
NAMES = ["whisper_verbose_json.json", "error_401.json", "error_400.json"]


def _load(name):
    return json.loads((FIXTURES / name).read_bytes().decode("utf-8"))


def test_whisper_fixture_shape_is_pinned():
    body = _load("whisper_verbose_json.json")
    assert sorted(body) == ["duration", "language", "segments", "task", "text", "usage", "words"]
    assert len(body["words"]) == 36
    assert body["duration"] == 16.92
    assert body["words"][-1]["start"] == 15.989999947547913


def test_error_fixtures_match_contract_bodies():
    assert _load("error_401.json") == {"error": {"message": "User not found.", "code": 401}}
    assert _load("error_400.json") == {
        "error": {"message": "Model openai/whisper-no-such-model does not exist", "code": 400}
    }


def test_no_secret_markers_in_any_fixture():  # security criterion 1: key leak into the committed repo
    for name in NAMES:
        text = (FIXTURES / name).read_text(encoding="utf-8")
        assert "sk-" not in text
        assert "Authorization" not in text

