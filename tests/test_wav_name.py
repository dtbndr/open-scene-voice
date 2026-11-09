import pytest

from scenevoice.synth.wav_name import wav_name


@pytest.mark.parametrize(
    ("ordinal", "expected"), [(1, "001.wav"), (9, "009.wav"), (10, "010.wav"), (42, "042.wav"), (999, "999.wav")]
)
def test_wav_name_zero_pads_to_three_digits(ordinal, expected):
    assert wav_name(ordinal) == expected
