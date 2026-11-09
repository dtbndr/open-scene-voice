from scenevoice.synth import AUDIO_DIR, audio_rel_path, wav_name


def test_constant_is_audio():
    assert AUDIO_DIR == "audio"


def test_helper_returns_relative_path_with_forward_slash():
    assert audio_rel_path(1) == "audio/001.wav"
    assert audio_rel_path(999) == "audio/999.wav"


def test_wav_name_stays_bare():
    assert wav_name(1) == "001.wav"
