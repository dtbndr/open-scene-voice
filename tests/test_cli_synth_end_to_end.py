import io
import json
import sys
import wave
from pathlib import Path

import pytest
from wav_helper import vertex_wav_response, wav_audio

from scenevoice.align import ALIGN_ENV_NAMES
from scenevoice.cli.main import main
from scenevoice.plan import serialize_plan
from scenevoice.synth import (
    ELEVENLABS_ENV_NAMES,
    ENV_NAMES,
    VERTEX,
    make_vertex_provider,
)
from scenevoice.validation import load_scenes

ROOT = Path(__file__).resolve().parent.parent
FRAMES = 5
AUDIO = wav_audio(FRAMES)


class Stdin:
    def __init__(self, data):
        self.buffer = io.BytesIO(data)

    def isatty(self):
        return False


class Fake:
    def __init__(self):
        self.factory_calls = 0
        self.calls = []

    def factory(self, env, model):
        self.factory_calls += 1

        def provider(request):
            body = request.body
            voice = request.voice
            language = request.language
            style = request.instruction
            self.calls.append((body, voice, language, style))
            return AUDIO

        return provider


def plan_bytes(name):
    result = load_scenes((ROOT / name).read_bytes())
    return serialize_plan(result).encode("utf-8")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ENV_NAMES:
        monkeypatch.setenv(name, "dummy-value")
    return tmp_path


@pytest.mark.parametrize("script", ["sample/scripts/short.md", "sample/scripts/long.md"])
@pytest.mark.parametrize("via", ["file", "stdin"])
def test_writes_one_valid_wav_per_scene(env, capsys, monkeypatch, script, via):
    data = plan_bytes(script)
    scene_count = len(json.loads(data)["scenes"])
    out = env / "out"
    args = ["synth", "--out", str(out), "--voice", "Charon", "--model", "gemini-3.8-flash-tts"]
    if via == "file":
        plan = env / "plan.json"
        plan.write_bytes(data)
        args.insert(1, str(plan))
    else:
        monkeypatch.setattr("sys.stdin", Stdin(data))
    fake = Fake()
    code = main(args, provider_factory=fake.factory)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert captured.err.splitlines()[-1].startswith("scenevoice synth: OK")
    wavs = sorted((out / "audio").glob("*.wav"))
    assert scene_count >= 1
    assert len(wavs) == scene_count == len(fake.calls)
    assert len(list((out / "audio").iterdir())) == scene_count
    assert sorted(p.name for p in out.iterdir()) == ["audio", "synth_record.json"]
    for path in wavs:
        with wave.open(str(path), "rb") as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (
                24000,
                1,
                2,
            )
            assert w.getnframes() == FRAMES


def test_rerun_into_same_directory_is_refused(env, capsys):
    plan = env / "plan.json"
    plan.write_bytes(plan_bytes("sample/scripts/short.md"))
    args = ["synth", str(plan), "--out", str(env / "out"), "--voice", "Charon", "--model", "gemini-3.8-flash-tts"]
    assert main(args, provider_factory=Fake().factory) == 0
    capsys.readouterr()
    again = Fake()
    assert main(args, provider_factory=again.factory) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines()[-1].startswith("scenevoice synth: FAIL")
    assert again.calls == []


def test_missing_env_fails_without_directory_or_real_factory(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("sys.stdin", Stdin(plan_bytes("sample/scripts/short.md")))
    called = []
    monkeypatch.setattr(
        sys.modules["scenevoice.cli.main"],
        "make_vertex_provider",
        lambda env, model: called.append(env),
    )
    out = tmp_path / "out"
    code = main(["synth", "--out", str(out), "--voice", "Charon", "--model", "gemini-3.8-flash-tts"])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    lines = [ln for ln in captured.err.splitlines() if ln]
    assert len(lines) == 1 and lines[0].startswith("scenevoice synth: FAIL")
    positions = [lines[0].index(name) for name in ENV_NAMES]
    assert positions == sorted(positions)
    assert not out.exists()
    assert called == []


def test_values_from_dotenv_in_cwd_are_used(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text("".join(f"{n}=dummy-value\n" for n in ENV_NAMES))
    monkeypatch.setattr("sys.stdin", Stdin(plan_bytes("sample/scripts/short.md")))
    fake = Fake()
    code = main(
        ["synth", "--out", str(tmp_path / "out"), "--voice", "Charon", "--model", "gemini-3.8-flash-tts"],
        provider_factory=fake.factory,
    )
    assert code == 0 and fake.factory_calls == 1
    assert capsys.readouterr().out == ""


def test_env_example_matches_env_names():
    lines = (ROOT / ".env.example").read_text().splitlines()
    assert [ln for ln in lines if ln and not ln.startswith("#")] == [
        *(f"{name}=" for name in ENV_NAMES),
        *(f"{name}=" for name in ELEVENLABS_ENV_NAMES),  # the ElevenLabs key after the Vertex names
        *(f"{name}=" for name in ALIGN_ENV_NAMES),  # the align key last
    ]


def run_through_real_adapter(env, model, voice):
    """Drive main with the real make_vertex_provider and a fake post (no network)."""
    posts = []

    def post(url, headers, body, timeout):
        posts.append((url, json.loads(body.decode("utf-8"))))
        return vertex_wav_response(FRAMES)

    plan = env / "plan.json"
    plan.write_bytes(plan_bytes("sample/scripts/short.md"))
    out = env / f"out-{model}"
    code = main(
        ["synth", str(plan), "--out", str(out), "--voice", voice, "--model", model],
        provider_factory=lambda e, m: make_vertex_provider(e, m, post=post),
    )
    return code, out, posts


def test_both_models_run_through_the_injected_post(env, capsys):
    scene_count = len(json.loads(plan_bytes("sample/scripts/short.md"))["scenes"])
    for model in VERTEX.models:
        code, out, posts = run_through_real_adapter(env, model, "Puck")
        capsys.readouterr()
        assert code == 0
        assert len(posts) == scene_count >= 1  # positive control: post called once per scene
        for url, body in posts:
            assert f"/models/{model}:generateContent" in url
            assert body["generationConfig"]["speechConfig"]["voiceConfig"]["voice"] == "Puck"
        wavs = sorted((out / "audio").glob("*.wav"))
        assert len(wavs) == scene_count
        for path in wavs:
            with wave.open(str(path), "rb") as w:
                assert (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()) == (
                    24000, 1, 2, FRAMES)


def test_scene_regenerates_only_that_scene(env, capsys):
    plan = env / "plan.json"
    plan.write_text(json.dumps({"scenes": [
        {"ordinal": 1, "title": "a", "body": "body one"},
        {"ordinal": 2, "title": "b", "body": "body two"},
    ]}))
    out = env / "out"
    base = ["synth", str(plan), "--out", str(out), "--voice", "Charon", "--model", "gemini-3.8-flash-tts"]
    assert main(base, provider_factory=Fake().factory) == 0
    first = (out / "audio" / "001.wav").read_bytes()
    capsys.readouterr()
    again = Fake()
    assert main([*base, "--scene", "2"], provider_factory=again.factory) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert [c[0] for c in again.calls] == ["body two"]
    assert (out / "audio" / "001.wav").read_bytes() == first
    assert sorted(p.name for p in (out / "audio").iterdir()) == ["001.wav", "002.wav"]
    assert sorted(p.name for p in out.iterdir()) == ["audio", "synth_record.json"]
    with wave.open(str(out / "audio" / "002.wav"), "rb") as w:
        assert w.getnframes() == FRAMES
