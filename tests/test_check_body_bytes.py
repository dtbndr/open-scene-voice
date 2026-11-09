import pytest

from scenevoice.synth.check_body_bytes import check_body_bytes
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.validation import Violation


def sized(n, total):
    return PlanScene(n, "", "a" * total)


def test_exactly_limit_passes():
    assert check_body_bytes([sized(1, 8000)], "gemini-3.8-flash-tts") is None


def test_one_over_fails():
    result = check_body_bytes([sized(1, 8001)], "gemini-3.8-flash-tts")
    assert result == Violation("synth-limit", "body over 8000 UTF-8 bytes: scene 1: 8001 bytes")


def test_multibyte_counted_in_bytes():
    scene = PlanScene(1, "", "é" * 4001)
    assert check_body_bytes([scene], "m") is not None
    assert check_body_bytes([PlanScene(1, "", "é" * 4000)], "m") is None


def test_all_offenders_named_in_plan_order():
    scenes = [sized(1, 10), sized(2, 8123), sized(3, 10), sized(5, 9001)]
    result = check_body_bytes(scenes, "m")
    assert result.message == "body over 8000 UTF-8 bytes: scene 2: 8123 bytes; scene 5: 9001 bytes"


@pytest.mark.parametrize("model", ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts", ""])
def test_model_is_ignored(model):
    assert check_body_bytes([sized(1, 8001)], model) == check_body_bytes([sized(1, 8001)], "x")


def test_does_not_check_scene_count():
    assert check_body_bytes([sized(n, 1) for n in range(1, 1100)], "m") is None
