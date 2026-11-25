import io
import json
from collections import namedtuple

from wav_helper import wav_audio

from scenevoice.synth import run_synth

ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "SeCrEt-key-0123456789",
}
PREFIX = "scenevoice synth: "
OLD = b"OLD-BYTES-DISTINGUISHABLE"
NEW_AUDIO = wav_audio(frames=20)
Call = namedtuple("Call", "body voice language style")


class Rec:
    def __init__(self, impl=None):
        self.factory_calls = 0
        self.calls = []
        self.impl = impl

    def factory(self, env, model):
        self.factory_calls += 1

        def provider(request):
            body = request.body
            voice = request.voice
            language = request.language
            style = request.instruction
            self.calls.append(Call(body, voice, language, style))
            if self.impl is not None:
                return self.impl()
            return NEW_AUDIO

        return provider


def make_plan(tmp_path, n=3, bodies=None):
    scenes = [
        {"ordinal": i, "title": "t", "body": (bodies or {}).get(i, f"body {i}")}
        for i in range(1, n + 1)
    ]
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"scenes": scenes}))
    return path


def make_out(tmp_path, names=("001.wav", "002.wav", "003.wav")):
    out = tmp_path / "out"
    (out / "audio").mkdir(parents=True)
    for name in names:
        (out / "audio" / name).write_bytes(OLD + name.encode())
    return out


def run(tmp_path, rec, scene=2, plan=None, env=ENV, **kw):
    stderr = io.StringIO()
    args = dict(
        plan_path=plan if plan is not None else make_plan(tmp_path),
        stdin=None,
        process_env=env,
        dotenv_path=tmp_path / "missing.env",
        out_dir=tmp_path / "out",
        voice="Callirrhoe",
        model="gemini-3.8-flash-tts",
        language="en-GB",
        instruction="calm",
        provider_factory=rec.factory,
        stderr=stderr,
        scene=scene,
    )
    args.update(kw)
    code = run_synth(**args)
    return code, stderr.getvalue()


def snapshot(out):
    return {p.name: p.read_bytes() for p in (out / "audio").iterdir()}


def no_temp(out):
    return [p.name for p in (out / "audio").iterdir() if p.name.startswith(".write-")] == []

