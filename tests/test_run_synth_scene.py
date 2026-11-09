import io
import json
import os
import sys
from collections import namedtuple

import pytest
from wav_helper import make_wav, wav_audio

from scenevoice.synth import ProviderAudio, ProviderError, run_synth

WRITE_MODULE = "scenevoice.synth.write_wav"
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


def test_replaces_only_selected_scene_with_one_call(tmp_path, capsys):
    out = make_out(tmp_path)
    before = snapshot(out)
    rec = Rec()
    code, err = run(tmp_path, rec, scene=2)
    assert code == 0
    assert rec.calls == [Call("body 2", "Callirrhoe", "en-GB", "calm")]
    after = snapshot(out)
    assert after["002.wav"] == NEW_AUDIO.wav != before["002.wav"]
    assert after["001.wav"] == before["001.wav"]
    assert after["003.wav"] == before["003.wav"]
    assert no_temp(out)
    assert capsys.readouterr().out == ""
    assert err.splitlines() == [
        PREFIX + "NOTE no settings recorded for scene 2 (synth_record.json is missing); settings not checked",
        PREFIX + "scene 2/3 written to audio/002.wav",
        PREFIX + f"OK scene 2 written to {out / 'audio' / '002.wav'}",
    ]
    assert rec.factory_calls == 1


def test_absent_target_is_created(tmp_path):
    out = make_out(tmp_path, names=("001.wav",))
    code, err = run(tmp_path, Rec(), scene=3)
    assert code == 0
    assert (out / "audio" / "003.wav").read_bytes() == NEW_AUDIO.wav
    assert err.splitlines()[0] == PREFIX + "NOTE no settings recorded for scene 3 (synth_record.json is missing); settings not checked"
    assert err.splitlines()[1] == PREFIX + "scene 3/3 written to audio/003.wav"


def test_one_scene_plan(tmp_path):
    out = make_out(tmp_path, names=("001.wav",))
    rec = Rec()
    code, err = run(tmp_path, rec, scene=1, plan=make_plan(tmp_path, n=1))
    assert code == 0
    assert len(rec.calls) == 1
    assert err.splitlines() == [
        PREFIX + "NOTE no settings recorded for scene 1 (synth_record.json is missing); settings not checked",
        PREFIX + "scene 1/1 written to audio/001.wav",
        PREFIX + f"OK scene 1 written to {out / 'audio' / '001.wav'}",
    ]


def _bad(audio):
    return lambda: audio


@pytest.mark.parametrize(
    "impl",
    [
        lambda: (_ for _ in ()).throw(ProviderError("boom")),
        _bad(ProviderAudio("audio/mpeg", make_wav())),
        _bad(ProviderAudio("audio/wav", b"not a wav at all")),
        _bad(ProviderAudio("audio/wav", make_wav()[:30])),
    ],
    ids=["provider-error", "wrong-media-type", "malformed-header", "truncated"],
)
def test_failures_keep_old_file(tmp_path, impl):
    out = make_out(tmp_path)
    before = snapshot(out)
    rec = Rec(impl)
    code, err = run(tmp_path, rec, scene=2)
    assert code == 1
    assert err.splitlines()[-1].startswith(PREFIX + "FAIL ")
    assert len(rec.calls) == 1
    assert snapshot(out) == before
    assert no_temp(out)


def test_write_failure_keeps_old_file(tmp_path, monkeypatch):
    out = make_out(tmp_path)
    before = snapshot(out)
    reached = []
    mod = sys.modules[WRITE_MODULE]

    def boom(src, dst):
        reached.append(dst)
        raise OSError("rename failed")

    monkeypatch.setattr(mod.os, "replace", boom)
    code, err = run(tmp_path, Rec(), scene=2)
    assert reached, "positive control: the patched os.replace was reached"
    assert code == 1
    assert err.splitlines()[-1].startswith(PREFIX + "FAIL ")
    assert snapshot(out) == before
    assert no_temp(out)


def test_unsearchable_out_dir_fails_cleanly(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    out = make_out(tmp_path)
    rec = Rec()
    (out / "audio").chmod(0)
    try:
        code, err = run(tmp_path, rec, scene=2)
    finally:
        (out / "audio").chmod(0o755)
    assert code == 1
    assert err.splitlines()[-1].startswith(PREFIX + "FAIL ")
    assert "002.wav" in err
    assert rec.factory_calls == 0 and rec.calls == []


def test_full_run_unchanged_without_scene(tmp_path):
    plan = make_plan(tmp_path)
    rec = Rec()
    code, err = run(tmp_path, rec, scene=None, plan=plan)
    out = tmp_path / "out"
    assert code == 0 and len(rec.calls) == 3
    assert err.splitlines()[-1] == PREFIX + f"OK 3 scenes written to {out}"
    assert err.splitlines()[0] == PREFIX + "scene 1/3 written to audio/001.wav"
    rec2 = Rec()
    code, err = run(tmp_path, rec2, scene=None, plan=plan)
    assert code == 1 and "001.wav" in err and rec2.factory_calls == 0
