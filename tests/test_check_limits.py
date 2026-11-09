import inspect

import pytest

from scenevoice.synth.check_limits import check_limits
from scenevoice.synth.limits import MAX_SCENES, MAX_TEXT_BYTES
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.validation import Violation


def scene(n, body):
    return PlanScene(n, "", body)


def sized(n, total):
    return scene(n, "a" * total)


def test_constants():
    assert (MAX_TEXT_BYTES, MAX_SCENES) == (8000, 999)


def test_exactly_limit_accepted():
    assert check_limits([sized(1, 8000)]) is None


def test_one_over_rejected():
    result = check_limits([sized(1, 8001)])
    assert isinstance(result, Violation)
    assert result.message == "body over 8000 UTF-8 bytes: scene 1: 8001 bytes"


def test_bytes_not_characters():
    chars = 8000 // 3
    ok = scene(1, "日" * chars)  # 7998 bytes
    assert check_limits([ok]) is None
    over = scene(1, "日" * (chars + 1))  # 8001 bytes, only 2667 characters
    result = check_limits([over])
    assert isinstance(result, Violation)
    assert result.message == "body over 8000 UTF-8 bytes: scene 1: 8001 bytes"


def test_names_every_offender():
    scenes = [sized(1, 8001), sized(2, 10), sized(3, 8500)]
    result = check_limits(scenes)
    assert result.message == (
        "body over 8000 UTF-8 bytes: scene 1: 8001 bytes; scene 3: 8500 bytes"
    )


def test_takes_no_instruction_parameter():
    params = inspect.signature(check_limits).parameters
    positional = [
        name
        for name, p in params.items()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    assert positional == ["scenes"]
    assert "instruction" not in params
    with pytest.raises(TypeError):
        check_limits([scene(1, "x")], "instruction")


def test_999_scenes_pass():
    assert check_limits([scene(i, "x") for i in range(1, 1000)]) is None


def test_1000_scenes_rejected_with_count_first():
    scenes = [sized(i, 9000) for i in range(1, 1001)]
    result = check_limits(scenes)
    assert isinstance(result, Violation)
    assert "1000" in result.message
    assert "9000" not in result.message
    assert "body over" not in result.message
