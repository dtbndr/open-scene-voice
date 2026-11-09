import sys

from wav_helper import wav_audio

from scenevoice.synth import PlanScene, ProviderAudio, synth_scenes

SCENES = [PlanScene(1, "t1", "body one"), PlanScene(2, "t2", "body two"), PlanScene(3, "t3", "body three")]
GOOD = wav_audio(24)


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, request):
        body = request.body
        self.calls.append(body)
        return GOOD


def run(tmp_path, provider, progress, plan=SCENES, **kw):
    (tmp_path / "audio").mkdir(exist_ok=True)
    return synth_scenes(SCENES, None, "Kore", "en-US", tmp_path, provider, progress, plan=SCENES, **kw)


def wavs(tmp_path):
    return sorted(p.name for p in (tmp_path / "audio").glob("*.wav"))


def test_no_hook_return_files_and_progress_unchanged(tmp_path):
    # Characterization: passes on main, no red step.
    lines = []
    rec = Recorder()
    assert run(tmp_path, rec, lines.append) is None
    assert lines == [f"scene {n}/3 written to audio/00{n}.wav" for n in (1, 2, 3)]
    assert wavs(tmp_path) == ["001.wav", "002.wav", "003.wav"]
    assert len(rec.calls) == 3


def test_hook_called_once_per_scene_after_wav_before_progress(tmp_path):
    events = []

    def hook(ordinal, audio):
        events.append(("hook", ordinal, wavs(tmp_path), len([e for e in events if e[0] == "progress"])))
        assert isinstance(audio, ProviderAudio)
        return None

    run(tmp_path, Recorder(), lambda m: events.append(("progress", m)), record_hook=hook)
    hooks = [e for e in events if e[0] == "hook"]
    assert [h[1] for h in hooks] == [1, 2, 3]
    # at hook n: WAV n exists and only n-1 progress lines were printed
    assert [h[2] for h in hooks] == [["001.wav"], ["001.wav", "002.wav"], ["001.wav", "002.wav", "003.wav"]]
    assert [h[3] for h in hooks] == [0, 1, 2]


def test_hook_message_stops_run_and_keeps_wavs(tmp_path):
    lines = []
    seen = []

    def hook(ordinal, audio):
        seen.append(ordinal)
        return "could not write synth_record.json" if ordinal == 2 else None

    rec = Recorder()
    msg = run(tmp_path, rec, lines.append, record_hook=hook)
    assert msg == "scene 2: could not write synth_record.json"
    assert seen == [1, 2]  # positive control: hook reached scene 2
    assert len(rec.calls) == 2
    assert wavs(tmp_path) == ["001.wav", "002.wav"]
    assert lines == ["scene 1/3 written to audio/001.wav"]


def test_hook_not_called_when_wav_write_fails(tmp_path, monkeypatch):
    mod = sys.modules["scenevoice.synth.synth_scenes"]
    writes = []

    def fake(out_dir, ordinal, wav):
        writes.append(ordinal)
        from scenevoice.validation import Violation

        return Violation("out-dir", "could not write 001.wav")

    monkeypatch.setattr(mod, "write_wav", fake)
    seen = []
    msg = run(tmp_path, Recorder(), lambda m: None, record_hook=lambda o, a: seen.append(o))
    assert writes == [1] and seen == []
    assert msg == "scene 1: could not write 001.wav"

