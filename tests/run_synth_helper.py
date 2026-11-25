"""Shared in-process run_synth driver for the full-run tests (not the --scene tests: see synth_scene_helper)."""

import io
import json
from collections import namedtuple

from common_helper import Stdin
from wav_helper import wav_audio

from scenevoice.synth import run_synth

KEY = "SeCrEt-key-0123456789"
ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": KEY,
}
AUDIO = wav_audio()
PREFIX = "scenevoice synth: "
Call = namedtuple("Call", "body voice language style env_count")


def plan_json(n=3, title="a title"):
    scenes = [{"ordinal": i, "title": title, "body": f"body {i}"} for i in range(1, n + 1)]
    return json.dumps({"scenes": scenes})


class Recorder:
    def __init__(self, provider=None, factory_error=None):
        self.envs = []
        self.models = []
        self.calls = []
        self.provider_impl = provider
        self.factory_error = factory_error

    def factory(self, env, model):
        self.envs.append(env)
        self.models.append(model)
        if self.factory_error is not None:
            raise self.factory_error

        def provider(request):
            self.calls.append(
                Call(request.body, request.voice, request.language, request.instruction, len(self.envs))
            )
            if self.provider_impl is not None:
                return self.provider_impl(len(self.calls))
            return AUDIO

        return provider


def run(tmp_path, rec, plan=None, stdin=None, stderr=None, env=ENV, **kw):
    stderr = stderr if stderr is not None else io.StringIO()
    if plan is None and stdin is None:
        plan = tmp_path / "plan.json"
        plan.write_text(plan_json())
    args = dict(
        plan_path=plan,
        stdin=stdin if stdin is not None else Stdin("", tty=True),
        process_env=env,
        dotenv_path=tmp_path / "missing.env",
        out_dir=tmp_path / "out",
        voice="Callirrhoe",
        model="gemini-3.8-flash-tts",
        language="en-GB",
        instruction=None,
        provider_factory=rec.factory,
        stderr=stderr,
    )
    args.update(kw)
    code = run_synth(**args)
    return code, stderr.getvalue() if isinstance(stderr, io.StringIO) else ""


def wavs(tmp_path):
    return sorted(p.name for p in (tmp_path / "out" / "audio").iterdir())
