from scenevoice.synth import Alignment, clamp_alignment


def _v4():
    return Alignment(("I", "t", " "), (0.0, 0.08, 0.16), (0.08, 0.16, 0.24))


def test_times_beyond_duration_are_clamped():
    result = clamp_alignment(_v4(), 0.15)
    assert result.character_start_times_seconds == (0.0, 0.08, 0.15)
    assert result.character_end_times_seconds == (0.08, 0.15, 0.15)


def test_characters_unchanged():
    assert clamp_alignment(_v4(), 0.15).characters == ("I", "t", " ")


def test_nothing_changes_when_all_times_fit():
    alignment = _v4()
    assert clamp_alignment(alignment, 1.0) == alignment
