"""run_synth full runs: success output, failures keeping earlier WAVs, and zero provider calls after a failed preflight."""

import sys

import pytest
from run_synth_helper import ENV, KEY, PREFIX, Recorder, Stdin, plan_json, run, wavs
from wav_helper import make_wav

from scenevoice.synth import ProviderAudio, ProviderError
from scenevoice.validation import Violation

RUN_MODULE = "scenevoice.synth.run_synth"
LOOP_MODULE = "scenevoice.synth.synth_scenes"


@pytest.mark.parametrize("source", ["path", "stdin"])
def test_success_writes_every_scene_with_prefixed_progress_and_empty_stdout(tmp_path, capsys, source):
    kw = {"stdin": Stdin(plan_json())} if source == "stdin" else {}
    code, err = run(tmp_path, Recorder(), **kw)
    assert code == 0
    assert wavs(tmp_path) == ["001.wav", "002.wav", "003.wav"]
    lines = err.splitlines()
    assert lines[:3] == [PREFIX + f"scene {n}/3 written to audio/00{n}.wav" for n in (1, 2, 3)]
    assert len(lines) == 4 and lines[3].startswith(PREFIX + "OK")
    assert capsys.readouterr().out == ""


def assert_failed_after_first(tmp_path, code, err):
    assert code == 1
    assert wavs(tmp_path) == ["001.wav"]
    lines = err.splitlines()
    assert lines[0] == PREFIX + "scene 1/3 written to audio/001.wav"
    assert lines[-1].startswith(PREFIX + "FAIL scene 2: ") and len(lines) == 2


def test_provider_error_on_scene_two_keeps_scene_one(tmp_path):
    def impl(n):
        if n == 2:
            raise ProviderError("quota exceeded")
        return ProviderAudio("audio/wav", make_wav())

    code, err = run(tmp_path, Recorder(provider=impl))
    assert_failed_after_first(tmp_path, code, err)
    assert "quota exceeded" in err


def test_invalid_audio_on_scene_two_keeps_scene_one(tmp_path):
    bad = ProviderAudio("audio/mpeg", make_wav())
    rec = Recorder(provider=lambda n: bad if n == 2 else ProviderAudio("audio/wav", make_wav()))
    code, err = run(tmp_path, rec)
    assert len(rec.calls) == 2  # positive control: scene 2 reached the provider
    assert_failed_after_first(tmp_path, code, err)
    assert "provider response rejected" in err


def test_write_failure_on_scene_two_keeps_scene_one(tmp_path, monkeypatch):
    mod = sys.modules[LOOP_MODULE]
    real = mod.write_wav
    seen = []

    def flaky(out_dir, ordinal, wav):
        seen.append(ordinal)
        if ordinal == 2:
            return Violation("synth-write", "cannot write 002.wav (disk full)")
        return real(out_dir, ordinal, wav)

    monkeypatch.setattr(mod, "write_wav", flaky)
    code, err = run(tmp_path, Recorder())
    assert seen == [1, 2]  # positive control: the patch is observed
    assert_failed_after_first(tmp_path, code, err)
    assert "disk full" in err


@pytest.mark.parametrize(
    "plan_text",
    [plan_json(1).replace("body 1", "x" * 8001), plan_json(1000)],
    ids=["over-8000-bytes", "1000-scenes"],
)
def test_over_limit_plan_is_rejected_before_any_io(tmp_path, plan_text):
    path = tmp_path / "plan.json"
    path.write_text(plan_text)
    rec = Recorder()
    code, err = run(tmp_path, rec, plan=path)
    assert code == 1 and err.splitlines()[-1].startswith(PREFIX + "FAIL")
    assert rec.envs == [] and rec.calls == [] and not (tmp_path / "out").exists()


def test_factory_is_called_once_with_the_resolved_env_before_any_provider_call(tmp_path, monkeypatch):
    mod = sys.modules[RUN_MODULE]
    real = mod.run_preflight
    results = []
    monkeypatch.setattr(mod, "run_preflight", lambda *a, **k: results.append(real(*a, **k)) or results[-1])
    rec = Recorder()
    code, _ = run(tmp_path, rec)
    assert code == 0 and len(results) == 1
    assert len(rec.envs) == 1 and rec.envs[0] == results[0].env
    assert len(rec.calls) == 3 and all(c.env_count == 1 for c in rec.calls)


def test_dotenv_only_configuration_reaches_the_factory(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("GOOGLE_CLOUD_PROJECT=p2\nGOOGLE_CLOUD_LOCATION=l2\nVERTEX_AUTHORIZATION_KEY=k2\n")
    rec = Recorder()
    code, _ = run(tmp_path, rec, env={}, dotenv_path=dotenv)
    assert code == 0
    assert rec.envs == [
        {"GOOGLE_CLOUD_PROJECT": "p2", "GOOGLE_CLOUD_LOCATION": "l2", "VERTEX_AUTHORIZATION_KEY": "k2"}
    ]


def failing_setups(tmp_path):
    good = tmp_path / "plan.json"
    good.write_text(plan_json(1))
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    (tmp_path / "taken" / "audio").mkdir(parents=True)
    (tmp_path / "taken" / "audio" / "001.wav").write_bytes(b"x")
    return {
        "terminal stdin": dict(plan=None, stdin=Stdin("", tty=True)),
        "invalid plan": dict(plan=bad),
        "missing env": dict(plan=good, env={}),
        "collision": dict(plan=good, out_dir=tmp_path / "taken"),
    }


@pytest.mark.parametrize("name", ["missing env", "collision"])
def test_factory_is_not_called_when_preflight_fails(tmp_path, name):
    rec = Recorder()
    code, err = run(tmp_path, rec, **failing_setups(tmp_path)[name])
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert rec.envs == [] and rec.calls == []


def test_factory_provider_error_is_a_failure_with_the_key_redacted(tmp_path, capsys):
    rec = Recorder(factory_error=ProviderError(f"auth failed for {KEY}\n and {KEY}"))
    code, err = run(tmp_path, rec, env={**ENV, "VERTEX_AUTHORIZATION_KEY": KEY + "\n"})
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert "auth failed" in err and KEY not in err and rec.calls == []
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["audio", "synth_record.json"]
    assert capsys.readouterr().out == ""
