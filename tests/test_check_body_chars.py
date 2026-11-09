
from scenevoice.synth.check_body_chars import check_body_chars
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.validation import Violation

V4 = "eleven_v4"
FLASH = "eleven_flash_v2_5"


def scene(n, body):
    return PlanScene(n, "", body)


def test_v4_exactly_limit_passes():
    assert check_body_chars([scene(1, "a" * 10000)], V4) is None


def test_v4_one_over_fails():
    assert check_body_chars([scene(1, "a" * 10001)], V4) == Violation(
        "synth-limit", "body over 10000 characters: scene 1: 10001 characters"
    )


def test_flash_limit_is_40000():
    assert check_body_chars([scene(1, "a" * 40000)], FLASH) is None
    assert check_body_chars([scene(1, "a" * 40001)], FLASH) == Violation(
        "synth-limit", "body over 40000 characters: scene 1: 40001 characters"
    )


def test_ten_thousand_and_one_passes_for_flash():
    assert check_body_chars([scene(1, "a" * 10001)], FLASH) is None


def test_counts_code_points_not_bytes():
    assert check_body_chars([scene(1, "é" * 10000)], V4) is None
    assert check_body_chars([scene(1, "\U0001f600" * 10000)], V4) is None
    assert check_body_chars([scene(1, "\U0001f600" * 10001)], V4) is not None


def test_all_offenders_named_in_plan_order():
    scenes = [scene(1, "a"), scene(2, "a" * 10123), scene(5, "a" * 12001)]
    result = check_body_chars(scenes, V4)
    assert result == Violation(
        "synth-limit",
        "body over 10000 characters: scene 2: 10123 characters; scene 5: 12001 characters",
    )


def test_ignores_the_scene_count():
    assert check_body_chars([scene(n, "a") for n in range(1, 1001)], V4) is None
