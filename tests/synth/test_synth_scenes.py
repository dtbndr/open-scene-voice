import sys
import wave

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
        self.requests = []
        self.responses = responses or {}

    def __call__(self, request):
        body = request.body
        voice = request.voice
        language = request.language
        style = request.instruction
        self.calls.append((body, voice, language, style))
        self.requests.append((body, voice, language, style, request.previous_text, request.next_text))
        r = self.responses.get(len(self.calls), GOOD)
        if isinstance(r, Exception):
            raise r
        return r


def run(tmp_path, provider, progress=None, **kw):
    (tmp_path / "audio").mkdir(exist_ok=True)
    return synth_scenes(SCENES, "Say:", "Kore", "en-US", tmp_path, provider,
                        progress or (lambda m: None), plan=SCENES, **kw)


def wavs(tmp_path):
    return sorted(p.name for p in (tmp_path / "audio").glob("*.wav"))


def test_success_calls_in_order_and_writes_valid_wavs(tmp_path):
    rec = Recorder()
    (tmp_path / "001.wav").write_bytes(b"flat")  # a flat WAV beside audio/ is never touched
    assert run(tmp_path, rec) is None
    assert (tmp_path / "001.wav").read_bytes() == b"flat"
    assert rec.calls == [(s.body, "Kore", "en-US", "Say:") for s in SCENES]
    assert wavs(tmp_path) == ["001.wav", "002.wav", "003.wav"]
    for name in wavs(tmp_path):
        with wave.open(str(tmp_path / "audio" / name)) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24000, 1, 2)
        assert (tmp_path / "audio" / name).read_bytes() == GOOD.wav
    assert not any("SECRET-TITLE" in c[0] for c in rec.calls)


def test_provider_error_stops_and_keeps(tmp_path):
    rec = Recorder({2: ProviderError("boom-text")})
    msg = run(tmp_path, rec)
    assert "boom-text" in msg
    assert len(rec.calls) == 2
    assert wavs(tmp_path) == ["001.wav"]


def test_invalid_audio_stops_and_keeps(tmp_path):
    rec = Recorder({2: ProviderAudio("audio/wav", make_wav(rate=16000))})
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


def test_progress_once_per_completed_scene_with_audio_paths_and_no_title(tmp_path, capsys):
    seen = []
    run(tmp_path, Recorder(), seen.append)
    assert seen == [f"scene {n}/3 written to audio/00{n}.wav" for n in (1, 2, 3)]
    assert not any("SECRET-TITLE" in m for m in seen)
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


def test_requests_carry_neighbours_from_the_whole_plan(tmp_path):
    plan = [PlanScene(i, f"t{i}", f"  body {i}\n") for i in (1, 2, 3)]
    full, one = Recorder(), Recorder()
    (tmp_path / "audio").mkdir()
    assert synth_scenes(plan, None, "Kore", "en-US", tmp_path, full, lambda m: None, plan=plan) is None
    assert [(r[4], r[5]) for r in full.requests] == [
        (None, plan[1].body), (plan[0].body, plan[2].body), (plan[1].body, None)]
    assert synth_scenes([plan[1]], None, "Kore", "en-US", tmp_path, one, lambda m: None, plan=plan, total=3) is None
    assert [(r[4], r[5]) for r in one.requests] == [(plan[0].body, plan[2].body)]


def test_hook_runs_after_the_wav_and_before_the_progress_line(tmp_path):
    events = []

    def hook(ordinal, audio):
        events.append(("hook", ordinal, wavs(tmp_path), sum(1 for e in events if e[0] == "progress")))
        assert isinstance(audio, ProviderAudio)

    run(tmp_path, Recorder(), lambda m: events.append(("progress", m)), record_hook=hook)
    hooks = [e for e in events if e[0] == "hook"]
    assert [h[1] for h in hooks] == [1, 2, 3]
    assert [h[2] for h in hooks] == [["001.wav"], ["001.wav", "002.wav"], ["001.wav", "002.wav", "003.wav"]]
    assert [h[3] for h in hooks] == [0, 1, 2]


def test_hook_message_stops_the_run_and_keeps_the_wavs(tmp_path):
    lines, seen = [], []

    def hook(ordinal, audio):
        seen.append(ordinal)
        return "could not write synth_record.json" if ordinal == 2 else None

    rec = Recorder()
    msg = run(tmp_path, rec, lines.append, record_hook=hook)
    assert msg == "scene 2: could not write synth_record.json"
    assert seen == [1, 2] and len(rec.calls) == 2  # positive control: hook reached scene 2
    assert wavs(tmp_path) == ["001.wav", "002.wav"]
    assert lines == ["scene 1/3 written to audio/001.wav"]


def test_hook_is_not_called_when_the_wav_write_fails(tmp_path, monkeypatch):
    mod = sys.modules["scenevoice.synth.synth_scenes"]
    writes, seen = [], []

    def fake(out_dir, ordinal, wav):
        writes.append(ordinal)
        return Violation("out-dir", "could not write 001.wav")

    monkeypatch.setattr(mod, "write_wav", fake)
    msg = run(tmp_path, Recorder(), lambda m: None, record_hook=lambda o, a: seen.append(o))
    assert writes == [1] and seen == []
    assert msg == "scene 1: could not write 001.wav"


# --- scene events and Failure carriers (WS40 slice E) ---


def events_run(tmp_path, provider, **kw):
    events = []
    result = run(tmp_path, provider, scene_event=lambda *a: events.append(a), **kw)
    return result, events


def test_scene_event_started_then_done_in_plan_order_with_one_message(tmp_path):
    lines = []
    result, events = events_run(tmp_path, Recorder(), progress=lines.append)
    assert result is None
    assert events == [
        item
        for n in (1, 2, 3)
        for item in (
            ("started", n, 3, None, f"scene {n}/3 started"),
            ("done", n, 3, f"audio/00{n}.wav", f"scene {n}/3 written to audio/00{n}.wav"),
        )
    ]
    assert lines == [e[4] for e in events if e[0] == "done"]


def test_scene_event_done_follows_the_record_hook(tmp_path):
    order = []
    run(
        tmp_path,
        Recorder(),
        scene_event=lambda state, n, *a: order.append((state, n)),
        record_hook=lambda n, audio: order.append(("hook", n)),
    )
    assert order[:3] == [("started", 1), ("hook", 1), ("done", 1)]


def test_quota_provider_error_is_a_failure_with_status(tmp_path):
    result = run(tmp_path, Recorder({2: ProviderError("slow down", status=429)}))
    assert result == "scene 2: slow down"
    assert (result.kind, result.scene, result.status) == ("quota", 2, 429)


def test_transport_provider_error_is_provider_down(tmp_path):
    result = run(tmp_path, Recorder({1: ProviderError("no route", transport=True)}))
    assert result == "scene 1: no route"
    assert (result.kind, result.scene, result.status) == ("provider_down", 1, None)
