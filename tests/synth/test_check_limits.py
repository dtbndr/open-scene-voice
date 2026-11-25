"""check_limits with an injected body check: count first, the injected result wins, the default is bytes."""

from scenevoice.synth import PlanScene, check_limits
from scenevoice.synth.check_body_bytes import check_body_bytes
from scenevoice.synth.check_body_chars import check_body_chars
from scenevoice.validation import Violation


def scene(n, body):
    return PlanScene(n, "", body)


def sized(n, total):
    return scene(n, "a" * total)


def test_names_every_offender():
    scenes = [sized(1, 8001), sized(2, 10), sized(3, 8500)]
    result = check_limits(scenes)
    assert result.message == (
        "body over 8000 UTF-8 bytes: scene 1: 8001 bytes; scene 3: 8500 bytes"
    )


def test_999_scenes_pass():
    assert check_limits([scene(i, "x") for i in range(1, 1000)]) is None


def test_1000_scenes_rejected_with_count_first():
    scenes = [sized(i, 9000) for i in range(1, 1001)]
    result = check_limits(scenes)
    assert isinstance(result, Violation)
    assert "1000" in result.message
    assert "9000" not in result.message
    assert "body over" not in result.message


def scenes(n=1, body="b"):
    return [PlanScene(i, "t", body) for i in range(1, n + 1)]


def test_count_is_checked_first_and_the_injected_check_is_not_called():
    calls = []

    def fake(items):
        calls.append(items)
        return None

    result = check_limits(scenes(1000), body_check=fake)
    assert result is not None and "1000 scenes exceeds the maximum of 999" in result.message
    assert calls == []
    assert check_limits(scenes(1), body_check=fake) is None
    assert len(calls) == 1


def test_the_injected_result_is_returned_as_is():
    verdict = Violation("x", "fake says no")
    assert check_limits(scenes(), body_check=lambda items: verdict) is verdict


def test_default_check_is_the_byte_limit():
    result = check_limits(scenes(1, "a" * 8001))
    assert result is not None
    assert result.message == "body over 8000 UTF-8 bytes: scene 1: 8001 bytes"


def sized_bytes(n, total):
    return PlanScene(n, "", "a" * total)


def test_bytes_exactly_limit_passes():
    assert check_body_bytes([sized_bytes(1, 8000)], "gemini-3.8-flash-tts") is None


def test_bytes_one_over_fails():
    result = check_body_bytes([sized_bytes(1, 8001)], "gemini-3.8-flash-tts")
    assert result == Violation("synth-limit", "body over 8000 UTF-8 bytes: scene 1: 8001 bytes")


def test_bytes_multibyte_counted_in_bytes():
    scene = PlanScene(1, "", "é" * 4001)
    assert check_body_bytes([scene], "m") is not None
    assert check_body_bytes([PlanScene(1, "", "é" * 4000)], "m") is None


def test_bytes_all_offenders_named_in_plan_order():
    scenes = [sized_bytes(1, 10), sized_bytes(2, 8123), sized_bytes(3, 10), sized_bytes(5, 9001)]
    result = check_body_bytes(scenes, "m")
    assert result.message == "body over 8000 UTF-8 bytes: scene 2: 8123 bytes; scene 5: 9001 bytes"


V4 = "eleven_v4"


FLASH = "eleven_flash_v2_5"


def test_chars_v4_exactly_limit_passes():
    assert check_body_chars([scene(1, "a" * 10000)], V4) is None


def test_chars_v4_one_over_fails():
    assert check_body_chars([scene(1, "a" * 10001)], V4) == Violation(
        "synth-limit", "body over 10000 characters: scene 1: 10001 characters"
    )


def test_chars_flash_limit_is_40000():
    assert check_body_chars([scene(1, "a" * 40000)], FLASH) is None
    assert check_body_chars([scene(1, "a" * 40001)], FLASH) == Violation(
        "synth-limit", "body over 40000 characters: scene 1: 40001 characters"
    )


def test_chars_counts_code_points_not_bytes():
    assert check_body_chars([scene(1, "é" * 10000)], V4) is None
    assert check_body_chars([scene(1, "\U0001f600" * 10000)], V4) is None
    assert check_body_chars([scene(1, "\U0001f600" * 10001)], V4) is not None


def test_chars_all_offenders_named_in_plan_order():
    scenes = [scene(1, "a"), scene(2, "a" * 10123), scene(5, "a" * 12001)]
    result = check_body_chars(scenes, V4)
    assert result == Violation(
        "synth-limit",
        "body over 10000 characters: scene 2: 10123 characters; scene 5: 12001 characters",
    )
