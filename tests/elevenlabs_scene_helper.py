"""Shared helpers for the ElevenLabs `synth --scene` tests (offline, injected post)."""

import json
from pathlib import Path

from scenevoice.cli.main import main
from scenevoice.synth import ELEVENLABS_ENV_NAMES, ENV_NAMES, make_elevenlabs_provider

FIXTURES = Path(__file__).parent / "fixtures" / "elevenlabs"
VOICE = "EXAVITQu4vr4xnSDxMaL"
FLASH, V4 = "eleven_flash_v2_5", "eleven_v4"
BODIES = ["First scene body.", "Second scene body.", "Third scene body."]
PREFIX = "scenevoice synth: "
DIFF = PREFIX + "FAIL scene 2 settings differ from synth_record.json: "
MALFORMED = (
    PREFIX + "FAIL synth_record.json is not a valid synth record "
    "(delete it to regenerate without a settings check)"
)


class FakePost:
    def __init__(self, fixture="success_flash.json"):
        self.fixture = fixture
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(json.loads(body.decode("utf-8")))
        return (FIXTURES / self.fixture).read_bytes()


def setup_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in (*ENV_NAMES, *ELEVENLABS_ENV_NAMES):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "dummy-eleven-key")
    plan = {"scenes": [{"ordinal": i + 1, "title": f"t{i}", "body": b}
                       for i, b in enumerate(BODIES)]}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    return tmp_path


def synth(capsys, post, *args):
    """Run main with an injected ElevenLabs factory; return (code, stderr)."""
    factory_calls = []

    def factory(env, model):
        factory_calls.append(model)
        return make_elevenlabs_provider(env, model, post=post)

    code = main(["synth", "plan.json", "--out", "out", *args], provider_factory=factory)
    captured = capsys.readouterr()
    assert captured.out == ""
    return code, captured.err


def el(model=FLASH, voice=VOICE, *extra):
    return ("--voice", voice, "--model", model, *extra)


def full_run(env, capsys, fixture="success_flash.json"):
    code, err = synth(capsys, FakePost(fixture), *el())
    assert code == 0, err
    return env / "out"


def records(out):
    return json.loads((out / "synth_record.json").read_text(encoding="utf-8"))["scenes"]


def untouched(out, run):
    wav = (out / "audio" / "002.wav").read_bytes()
    rec = (out / "synth_record.json").read_bytes()
    post = FakePost()
    code, err = run(post)
    assert (out / "audio" / "002.wav").read_bytes() == wav
    assert (out / "synth_record.json").read_bytes() == rec
    assert post.calls == []
    return code, err
