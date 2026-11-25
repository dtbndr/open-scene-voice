"""Beats segmenting, prompt and request body (WS35 slice F).

The request shape is unobserved: no live call has confirmed the provider
accepts it. These tests pin our own bytes only.
"""

import json
from pathlib import Path

from paths_helper import REPO_ROOT

from scenevoice.align.split_sentences import split_sentences
from scenevoice.beats.beats_constants import BEATS_MAX_TOKENS
from scenevoice.beats.build_beats_prompt import build_beats_prompt
from scenevoice.beats.build_beats_request import build_beats_request
from scenevoice.beats.segment_scenes import segment_scenes
from scenevoice.validation.scene import Scene

BODY_ONE = "First sentence here. Second one follows.\n\nNew paragraph, café ☕ stays."
SCENES = [
    Scene(ordinal=1, title="Intro à la carte", body=BODY_ONE, line=1),
    Scene(ordinal=2, title="Empty", body="   \n", line=5),
    Scene(ordinal=3, title="Outro", body="Bye now.", line=8),
]
GUIDE = REPO_ROOT / "docs" / "script-format.md"


def _messages():
    segments = segment_scenes(SCENES)
    return segments, build_beats_prompt(SCENES, segments)


def test_segment_scenes_is_split_sentences_per_scene():
    segments = segment_scenes(SCENES)
    assert segments == [split_sentences(s.body) for s in SCENES]
    assert segments[0] == [
        "First sentence here.",
        "Second one follows.",
        "New paragraph, café ☕ stays.",
    ]
    assert segments[1] == []


def test_system_message_states_each_required_element():
    _, messages = _messages()
    assert [m["role"] for m in messages] == ["system", "user"]
    system = messages[0]["content"]
    # Decision 6 reply shape, exactly.
    assert (
        '{"scenes": [{"scene": 1, "beats": [{"first": 1, "last": 2, "note": "..."}]}]}'
        in system
    )
    assert '"ordinal"' not in system
    # One phrase per required element (slices.md, Implementation discretion).
    assert "a single JSON object and nothing else" in system
    assert "contiguous" in system
    assert "in order" in system
    assert "exactly once" in system
    assert "single-line" in system
    assert "description of the picture" in system
    assert "describe only: no timing, no cues, no rewriting" in system
    assert "200" in system


def test_user_message_lists_scenes_and_numbered_segments_in_order():
    _, messages = _messages()
    user = messages[1]["content"]
    expected = [
        "Scene 1: Intro à la carte",
        "1. First sentence here.",
        "2. Second one follows.",
        "3. New paragraph, café ☕ stays.",
        "Scene 2: Empty",
        "(no segments)",
        "Scene 3: Outro",
        "1. Bye now.",
    ]
    positions = [user.index(e) for e in expected]
    assert positions == sorted(positions)


def test_empty_scene_shows_no_segments_line_and_no_numbered_line():
    _, messages = _messages()
    user_lines = messages[1]["content"].splitlines()
    at = user_lines.index("Scene 2: Empty")
    assert user_lines[at + 1] == "(no segments)"
    assert user_lines[at + 2] == ""
    assert user_lines[at + 3] == "Scene 3: Outro"


def test_prompt_has_no_environment_values(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret-value-123")
    _, messages = _messages()
    text = json.dumps(messages)
    assert "sk-secret-value-123" not in text
    assert str(Path.cwd()) not in text
    assert str(Path.home()) not in text


def test_prompt_excludes_script_format_guide():
    lines = GUIDE.read_text(encoding="utf-8").splitlines()
    heading = next(line for line in lines if line.strip())
    first_body = next(line for line in lines[lines.index(heading) + 1 :] if line.strip())
    _, messages = _messages()
    for message in messages:
        assert heading not in message["content"]
        assert first_body not in message["content"]


def test_request_body_bytes_fixed_order_and_no_response_format():
    _, messages = _messages()
    raw = build_beats_request("some/model", messages)
    assert raw == json.dumps(
        {"model": "some/model", "messages": messages, "max_tokens": BEATS_MAX_TOKENS}
    ).encode("utf-8")
    body = json.loads(raw)
    assert list(body) == ["model", "messages", "max_tokens"]
    assert body["max_tokens"] == BEATS_MAX_TOKENS
    assert "response_format" not in body
    assert "café ☕" in body["messages"][1]["content"]


def test_request_body_survives_lone_surrogate():
    raw = build_beats_request("m", [{"role": "user", "content": "x\ud800"}])
    assert json.loads(raw)["messages"][0]["content"] == "x\ud800"
