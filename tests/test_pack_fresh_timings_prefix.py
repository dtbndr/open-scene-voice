import hashlib

from scenevoice.pack import LineTiming, fresh_timings

WAV = b"wav-one"
REAL = hashlib.sha256(WAV).hexdigest()
LINES = [LineTiming("x", 0)]


def _other(char: str) -> str:
    return "0" if char != "0" else "1"


def test_hash_equal_for_first_eight_characters_only_is_stale():
    forged = REAL[:8] + _other(REAL[8]) + REAL[9:]
    result = fresh_timings({1: (forged, LINES)}, [(1, WAV)])
    assert result.fresh == {}
    assert result.unusable == [(1, "stale")]


def test_hash_equal_except_the_last_character_is_stale():
    forged = REAL[:-1] + _other(REAL[-1])
    assert len(forged) == len(REAL)
    result = fresh_timings({1: (forged, LINES)}, [(1, WAV)])
    assert result.fresh == {}
    assert result.unusable == [(1, "stale")]


def test_full_hash_is_fresh_control():
    result = fresh_timings({1: (REAL, LINES)}, [(1, WAV)])
    assert result.fresh == {1: LINES}
