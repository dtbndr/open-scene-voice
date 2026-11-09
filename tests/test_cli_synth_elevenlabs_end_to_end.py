"""synth with an ElevenLabs model through the real adapter and an injected post (no network)."""

import io
import json
import wave
from pathlib import Path

import pytest

from scenevoice.cli.main import main
from scenevoice.synth import ELEVENLABS_ENV_NAMES, ENV_NAMES, make_elevenlabs_provider
from scenevoice.synth.provider import ProviderError

FIXTURES = Path(__file__).parent / "fixtures" / "elevenlabs"
VOICE = "EXAVITQu4vr4xnSDxMaL"
URL = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=pcm_24000"
KEY = "dummy-eleven-key"
BODIES = ["First scene body.", "Second scene body.", "Third scene body."]
FLASH, V4 = "eleven_flash_v2_5", "eleven_v4"


class Stdin:
    def __init__(self, data):
        self.buffer = io.BytesIO(data)

    def isatty(self):
        return False


class FakePost:
    def __init__(self, fixtures=None, raises_at=None):
        self.fixtures = fixtures or {}
        self.raises_at = raises_at
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, json.loads(body.decode("utf-8"))))
        n = len(self.calls)
        if n == self.raises_at:
            raise ProviderError(f"HTTP 404 voice {KEY}")
        return (FIXTURES / self.fixtures.get(n, "success_flash.json")).read_bytes()


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in (*ENV_NAMES, *ELEVENLABS_ENV_NAMES):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", KEY)
    plan = {"scenes": [{"ordinal": i + 1, "title": f"t{i}", "body": b} for i, b in enumerate(BODIES)]}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    out = tmp_path / "out"

    def go(model, post, capsys):
        factory_calls = []

        def factory(env, m):
            factory_calls.append(m)
            return make_elevenlabs_provider(env, m, post=post)

        code = main(
            ["synth", "plan.json", "--out", str(out), "--voice", VOICE, "--model", model],
            provider_factory=factory)
        captured = capsys.readouterr()
        return code, captured, factory_calls

    go.out = out
    return go


def record(out):
    return json.loads((out / "synth_record.json").read_text(encoding="utf-8"))["scenes"]


@pytest.mark.parametrize("model", [FLASH, V4])
def test_full_run_posts_in_order_and_writes_wavs_and_record(run, capsys, model):
    fixture = "success_v4_overshoot.json" if model == V4 else "success_flash.json"
    post = FakePost({1: fixture, 2: fixture, 3: fixture})
    code, captured, _ = run(model, post, capsys)
    assert code == 0, captured.err
    assert captured.out == ""
    assert captured.err.rstrip().endswith(f"scenevoice synth: OK 3 scenes written to {run.out}")
    assert [c[0] for c in post.calls] == [URL] * 3
    assert [c[2]["text"] for c in post.calls] == BODIES
    assert all(c[2]["model_id"] == model and c[2]["seed"] == 42 for c in post.calls)
    assert list(post.calls[0][2]) == ["text", "model_id", "next_text", "seed"]
    assert post.calls[0][2]["next_text"] == BODIES[1]
    assert list(post.calls[1][2]) == ["text", "model_id", "previous_text", "next_text", "seed"]
    assert post.calls[1][2]["previous_text"] == BODIES[0] and post.calls[1][2]["next_text"] == BODIES[2]
    assert list(post.calls[2][2]) == ["text", "model_id", "previous_text", "seed"]
    assert post.calls[2][2]["previous_text"] == BODIES[1]
    frames = 3600 if model == V4 else 4800
    for n in (1, 2, 3):
        with wave.open(str(run.out / "audio" / f"00{n}.wav")) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()) == (
                24000, 1, 2, frames)
    entries = record(run.out)
    assert [e["ordinal"] for e in entries] == [1, 2, 3]
    assert all(
        e["language"] is None and e["instruction"] is None and e["model"] == model
        and e["voice"] == VOICE for e in entries)
    expected_end = [0.08, 0.15, 0.15] if model == V4 else [0.128, 0.186]
    assert entries[0]["alignment"]["character_end_times_seconds"] == expected_end


def test_empty_alignment_stops_the_run(run, capsys):
    code, captured, _ = run(FLASH, FakePost({2: "empty_arrays.json"}), capsys)
    assert code == 1 and captured.out == ""
    assert "scenevoice synth: FAIL scene 2: ElevenLabs response alignment is empty" in captured.err
    assert (run.out / "audio" / "001.wav").exists() and not (run.out / "audio" / "002.wav").exists()
    assert [e["ordinal"] for e in record(run.out)] == [1]


def test_provider_error_is_redacted(run, capsys):
    code, captured, _ = run(FLASH, FakePost(raises_at=1), capsys)
    assert code == 1 and captured.out == ""
    assert "scenevoice synth: FAIL scene 1: HTTP 404 voice [redacted]" in captured.err
    assert KEY not in captured.err


def test_missing_key_fails_before_the_factory_and_without_vertex_names(run, capsys, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    code, captured, factory_calls = run(FLASH, FakePost(), capsys)
    assert code == 1 and captured.out == ""
    assert captured.err.strip().splitlines()[-1] == (
        "scenevoice synth: FAIL missing environment variables: ELEVENLABS_API_KEY")
    assert factory_calls == [] and not run.out.exists()
