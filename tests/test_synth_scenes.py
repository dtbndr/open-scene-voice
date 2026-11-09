import sys
import wave

import pytest
from wav_helper import make_wav, wav_audio

from scenevoice.synth import PlanScene, ProviderAudio, ProviderError, synth_scenes
from scenevoice.validation import Violation

GOOD = wav_audio(24)
SCENES = [
    PlanScene(1, "SECRET-TITLE-ONE", "body one"),
    PlanScene(2, "SECRET-TITLE-TWO", "body two"),
    PlanScene(3, "SECRET-TITLE-THREE", "body three"),
]


class Recorder:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def __call__(self, request):
        body = request.body
        voice = request.voice
        language = request.language
        style = request.instruction
        self.calls.append((body, voice, language, style))
        r = self.responses.get(len(self.calls), GOOD)
        if isinstance(r, Exception):
            raise r
        return r


def run(tmp_path, provider, progress=None):
    (tmp_path / "audio").mkdir(exist_ok=True)
    return synth_scenes(SCENES, "Say:", "Kore", "en-US", tmp_path, provider,
                        progress or (lambda m: None), plan=SCENES)


def wavs(tmp_path):
    return sorted(p.name for p in (tmp_path / "audio").glob("*.wav"))


def test_success_calls_in_order_and_writes_valid_wavs(tmp_path):
    rec = Recorder()
    assert run(tmp_path, rec) is None
    assert rec.calls == [(s.body, "Kore", "en-US", "Say:") for s in SCENES]
    assert wavs(tmp_path) == ["001.wav", "002.wav", "003.wav"]
    for name in wavs(tmp_path):
        with wave.open(str(tmp_path / "audio" / name)) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24000, 1, 2)
        assert (tmp_path / "audio" / name).read_bytes() == GOOD.wav
    assert not any("SECRET-TITLE" in c[0] for c in rec.calls)


def test_none_instruction_reaches_provider_as_none_style(tmp_path):
    rec = Recorder()
    (tmp_path / "audio").mkdir()
    assert synth_scenes(SCENES, None, "Kore", "en-US", tmp_path, rec, lambda m: None, plan=SCENES) is None
    assert [c[3] for c in rec.calls] == [None, None, None]
    assert [c[0] for c in rec.calls] == [s.body for s in SCENES]


def test_provider_error_stops_and_keeps(tmp_path):
    rec = Recorder({2: ProviderError("boom-text")})
    msg = run(tmp_path, rec)
    assert "boom-text" in msg
    assert len(rec.calls) == 2
    assert wavs(tmp_path) == ["001.wav"]


@pytest.mark.parametrize(
    "bad",
    [
        ProviderAudio("audio/L16;codec=pcm;rate=24000", bytes(48)),
        ProviderAudio("audio/wav", make_wav(rate=16000)),
        ProviderAudio("audio/wav", make_wav()[:20]),
    ],
    ids=["l16-mime", "wrong-rate", "truncated-header"],
)
def test_invalid_audio_stops_and_keeps(tmp_path, bad):
    rec = Recorder({2: bad})
    msg = run(tmp_path, rec)
    assert isinstance(msg, str) and msg
    assert len(rec.calls) == 2
    assert wavs(tmp_path) == ["001.wav"]


def test_write_failure_stops_and_keeps(tmp_path, monkeypatch):
    mod = sys.modules["scenevoice.synth.synth_scenes"]
    real = mod.write_wav
    writes = []

    def fake(out_dir, ordinal, wav):
        writes.append(ordinal)
        if ordinal == 2:
            return Violation("out-dir", "could not write 002.wav")
        return real(out_dir, ordinal, wav)

    monkeypatch.setattr(mod, "write_wav", fake)
    rec = Recorder()
    msg = run(tmp_path, rec)
    assert writes == [1, 2]  # positive control: patch observed, failure reached
    assert "could not write 002.wav" in msg
    assert len(rec.calls) == 2
    assert wavs(tmp_path) == ["001.wav"]


def test_programming_error_surfaces(tmp_path):
    rec = Recorder({2: KeyError("bug")})
    with pytest.raises(KeyError):
        run(tmp_path, rec)


def test_progress_once_per_completed_scene_without_title(tmp_path, capsys):
    seen = []
    run(tmp_path, Recorder(), seen.append)
    assert len(seen) == 3
    assert not any("SECRET-TITLE" in m for m in seen)
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


def test_progress_not_called_for_failed_scene(tmp_path):
    seen = []
    run(tmp_path, Recorder({2: ProviderError("x")}), seen.append)
    assert len(seen) == 1
