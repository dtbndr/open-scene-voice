from wav_helper import wav_audio

from scenevoice.synth import PlanScene, synth_scenes

GOOD = wav_audio(24)
SCENES = [PlanScene(1, "t", "one"), PlanScene(2, "t", "two")]


def provider(request):
    return GOOD


def test_writes_into_audio_and_reports_audio_relative_path(tmp_path):
    (tmp_path / "audio").mkdir()
    seen = []
    result = synth_scenes(
        SCENES, None, "Kore", "en-US", tmp_path, provider, seen.append, plan=SCENES
    )
    assert result is None
    assert sorted(p.name for p in (tmp_path / "audio").iterdir()) == ["001.wav", "002.wav"]
    assert seen == [
        "scene 1/2 written to audio/001.wav",
        "scene 2/2 written to audio/002.wav",
    ]


def test_flat_wav_is_not_overwritten(tmp_path):
    (tmp_path / "audio").mkdir()
    (tmp_path / "001.wav").write_bytes(b"flat")
    synth_scenes(
        SCENES, None, "Kore", "en-US", tmp_path, provider, lambda m: None, plan=SCENES
    )
    assert (tmp_path / "001.wav").read_bytes() == b"flat"
