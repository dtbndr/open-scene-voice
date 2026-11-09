import io
import json
import os
import sys
from collections import namedtuple

import pytest
from wav_helper import make_wav, wav_audio

from scenevoice.synth import ProviderAudio, ProviderError, run_synth
from scenevoice.validation import Violation

RUN_MODULE = "scenevoice.synth.run_synth"
LOOP_MODULE = "scenevoice.synth.synth_scenes"
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


class Stdin:
    def __init__(self, text, tty=False):
        self.buffer = io.BytesIO(text.encode("utf-8"))
        self.tty = tty

    def isatty(self):
        return self.tty


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
            body = request.body
            voice = request.voice
            language = request.language
            style = request.instruction
            self.calls.append(Call(body, voice, language, style, len(self.envs)))
            if self.provider_impl is not None:
                return self.provider_impl(len(self.calls))
            return AUDIO

        return provider


def run(tmp_path, rec, plan=None, stdin=None, stderr=None, env=ENV, **kw):
    stderr = stderr if stderr is not None else io.StringIO()
    if plan is None and stdin is None:
        path = tmp_path / "plan.json"
        path.write_text(plan_json())
        plan = path
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


def assert_three_scene_progress(err):
    lines = err.splitlines()
    assert lines[:3] == [
        PREFIX + "scene 1/3 written to audio/001.wav",
        PREFIX + "scene 2/3 written to audio/002.wav",
        PREFIX + "scene 3/3 written to audio/003.wav",
    ]
    assert len(lines) == 4 and lines[3].startswith(PREFIX + "OK")
    assert all(line.startswith(PREFIX) for line in lines)


def test_run_from_path(tmp_path, capsys):
    code, err = run(tmp_path, Recorder())
    assert code == 0
    assert wavs(tmp_path) == ["001.wav", "002.wav", "003.wav"]
    assert_three_scene_progress(err)
    assert capsys.readouterr().out == ""


def test_run_from_stdin(tmp_path, capsys):
    code, err = run(tmp_path, Recorder(), stdin=Stdin(plan_json()))
    assert code == 0
    assert wavs(tmp_path) == ["001.wav", "002.wav", "003.wav"]
    assert_three_scene_progress(err)
    assert capsys.readouterr().out == ""


def test_progress_never_contains_title(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(plan_json(title="UNIQUE-TITLE-xyz"))
    code, err = run(tmp_path, Recorder(), plan=path)
    assert code == 0 and "UNIQUE-TITLE-xyz" not in err


def test_surrogate_title_does_not_crash_strict_stderr(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(plan_json(title="\ud800 bad"))
    raw = io.BytesIO()
    stderr = io.TextIOWrapper(raw, encoding="utf-8", errors="strict", write_through=True)
    code, _ = run(tmp_path, Recorder(), plan=path, stderr=stderr)
    assert code == 0
    assert b"scene 3/3 written to audio/003.wav" in raw.getvalue()


def assert_failed_after_first(tmp_path, code, err):
    assert code == 1
    assert wavs(tmp_path) == ["001.wav"]
    lines = err.splitlines()
    assert lines[0] == PREFIX + "scene 1/3 written to audio/001.wav"
    assert lines[-1].startswith(PREFIX + "FAIL scene 2: ")
    assert len(lines) == 2


def test_provider_error_on_scene_two(tmp_path):
    def impl(n):
        if n == 2:
            raise ProviderError("quota exceeded")
        return AUDIO

    code, err = run(tmp_path, Recorder(provider=impl))
    assert_failed_after_first(tmp_path, code, err)
    assert "quota exceeded" in err


INVALID = {
    "wrong-mime": ProviderAudio("audio/mpeg", make_wav()),
    "wrong-rate": ProviderAudio("audio/wav", make_wav(rate=16000)),
    "stereo": ProviderAudio("audio/wav", make_wav(channels=2)),
    "truncated-header": ProviderAudio("audio/wav", make_wav()[:20]),
}


@pytest.mark.parametrize("bad", INVALID.values(), ids=INVALID.keys())
def test_invalid_audio_on_scene_two(tmp_path, bad):
    rec = Recorder(provider=lambda n: bad if n == 2 else AUDIO)
    code, err = run(tmp_path, rec)
    assert len(rec.calls) == 2  # positive control: scene 2 reached the provider
    assert_failed_after_first(tmp_path, code, err)  # no 002.wav, 001.wav kept
    assert "provider response rejected" in err


@pytest.mark.parametrize(
    "plan_text",
    [plan_json(1).replace("body 1", "x" * 8001), plan_json(1000)],
    ids=["over-8000-bytes", "1000-scenes"],
)
def test_over_limit_plan_rejected_before_any_io(tmp_path, plan_text):
    path = tmp_path / "plan.json"
    path.write_text(plan_text)
    rec = Recorder()
    code, err = run(tmp_path, rec, plan=path)
    assert code == 1 and err.splitlines()[-1].startswith(PREFIX + "FAIL")
    assert rec.envs == [] and rec.calls == []
    assert not (tmp_path / "out").exists()


def test_write_failure_after_start(tmp_path, monkeypatch):
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


def preflight_spy(monkeypatch):
    mod = sys.modules[RUN_MODULE]
    real = mod.run_preflight
    results = []

    def spy(*args, **kwargs):
        result = real(*args, **kwargs)
        results.append(result)
        return result

    monkeypatch.setattr(mod, "run_preflight", spy)
    return results


def test_factory_called_once_with_resolved_env_before_provider(tmp_path, monkeypatch):
    results = preflight_spy(monkeypatch)
    rec = Recorder()
    code, _ = run(tmp_path, rec)
    assert code == 0 and len(results) == 1
    assert len(rec.envs) == 1 and rec.envs[0] == results[0].env
    assert len(rec.calls) == 3 and all(c.env_count == 1 for c in rec.calls)


def test_dotenv_only_configuration(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "GOOGLE_CLOUD_PROJECT=p2\nGOOGLE_CLOUD_LOCATION=l2\nVERTEX_AUTHORIZATION_KEY=k2\n"
    )
    rec = Recorder()
    code, _ = run(tmp_path, rec, env={}, dotenv_path=dotenv)
    assert code == 0
    assert rec.envs == [
        {
            "GOOGLE_CLOUD_PROJECT": "p2",
            "GOOGLE_CLOUD_LOCATION": "l2",
            "VERTEX_AUTHORIZATION_KEY": "k2",
        }
    ]


def failing_setups(tmp_path):
    good = tmp_path / "plan.json"
    good.write_text(plan_json(1))
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    (tmp_path / "taken" / "audio").mkdir(parents=True)
    (tmp_path / "taken" / "audio" / "001.wav").write_bytes(b"x")
    afile = tmp_path / "afile"
    afile.write_text("x")
    (tmp_path / "dangling").symlink_to(tmp_path / "no-such-target")
    return {
        "terminal stdin": dict(plan=None, stdin=Stdin("", tty=True)),
        "unreadable plan": dict(plan=tmp_path / "nope.json"),
        "invalid plan": dict(plan=bad),
        "missing env": dict(plan=good, env={}),
        "collision": dict(plan=good, out_dir=tmp_path / "taken"),
        "out is a file": dict(plan=good, out_dir=afile),
        "dangling symlink out": dict(plan=good, out_dir=tmp_path / "dangling"),
    }


@pytest.mark.parametrize(
    "name",
    ["terminal stdin", "unreadable plan", "invalid plan", "missing env", "collision", "out is a file", "dangling symlink out"],
)
def test_factory_not_called_when_preflight_fails(tmp_path, name):
    rec = Recorder()
    kwargs = failing_setups(tmp_path)[name]
    kwargs.setdefault("plan", None)
    code, err = run(tmp_path, rec, **kwargs)
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert rec.envs == [] and rec.calls == []


def test_factory_not_called_when_out_dir_unwritable(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        if os.access(locked, os.W_OK):
            pytest.skip("permissions are not enforced (e.g. running as root)")
        rec = Recorder()
        good = failing_setups(tmp_path)["missing env"]["plan"]
        code, err = run(tmp_path, rec, plan=good, out_dir=locked)
        assert code == 1 and err.startswith(PREFIX + "FAIL ")
        assert rec.envs == [] and rec.calls == []
    finally:
        locked.chmod(0o700)


def test_factory_positive_control_called_once_on_success(tmp_path):
    rec = Recorder()
    code, _ = run(tmp_path, rec, plan=failing_setups(tmp_path)["missing env"]["plan"])
    assert code == 0 and len(rec.envs) == 1


def test_factory_provider_error_is_provider_failure(tmp_path, capsys):
    rec = Recorder(factory_error=ProviderError(f"auth failed for {KEY}\n and {KEY}"))
    code, err = run(tmp_path, rec, env={**ENV, "VERTEX_AUTHORIZATION_KEY": KEY + "\n"})
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert "auth failed" in err and KEY not in err
    assert rec.calls == []
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["audio", "synth_record.json"]
    assert list((tmp_path / "out" / "audio").iterdir()) == []
    assert capsys.readouterr().out == ""


def test_factory_programming_error_surfaces(tmp_path):
    with pytest.raises(KeyError):
        run(tmp_path, Recorder(factory_error=KeyError("bug")))


def keyed_env():
    return {**ENV, "VERTEX_AUTHORIZATION_KEY": KEY + "\n"}


def leaky(n=0):
    raise ProviderError(f"boom {KEY}\n and {KEY} end")


def test_provider_error_redacts_key(tmp_path, capsys):
    code, err = run(tmp_path, Recorder(provider=leaky), env=keyed_env())
    assert code == 1 and "boom" in err and KEY not in err
    assert capsys.readouterr().out == ""


def test_provider_error_redacts_key_from_dotenv_only(tmp_path, capsys):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        f"GOOGLE_CLOUD_PROJECT=p\nGOOGLE_CLOUD_LOCATION=l\nVERTEX_AUTHORIZATION_KEY={KEY}\n"
    )
    code, err = run(tmp_path, Recorder(provider=leaky), env={}, dotenv_path=dotenv)
    assert code == 1 and "boom" in err and KEY not in err
    assert capsys.readouterr().out == ""


def test_factory_error_redacts_key_from_dotenv_only(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        f"GOOGLE_CLOUD_PROJECT=p\nGOOGLE_CLOUD_LOCATION=l\nVERTEX_AUTHORIZATION_KEY={KEY}\n"
    )
    rec = Recorder(factory_error=ProviderError(f"x {KEY}"))
    code, err = run(tmp_path, rec, env={}, dotenv_path=dotenv)
    assert code == 1 and "x " in err and KEY not in err


def test_preflight_failure_still_redacts_process_env_key(tmp_path, monkeypatch):
    code, err = run(tmp_path, Recorder(), plan=tmp_path / "nope.json", env=keyed_env())
    assert code == 1 and "FAIL" in err  # positive control: plain failure path
    mod = sys.modules[RUN_MODULE]
    calls = []

    def leaking(*args, **kwargs):
        calls.append(1)
        return f"leak {KEY}\n tail"

    monkeypatch.setattr(mod, "run_preflight", leaking)
    code, err = run(tmp_path, Recorder(), env=keyed_env())
    assert calls == [1] and code == 1
    assert "leak" in err and KEY not in err


def test_none_instruction_gives_provider_none_style_and_no_default(tmp_path):
    rec = Recorder()
    code, err = run(tmp_path, rec, instruction=None)
    assert code == 0
    assert [c.style for c in rec.calls] == [None, None, None]
    assert [c.body for c in rec.calls] == ["body 1", "body 2", "body 3"]


@pytest.mark.parametrize("style", ["Say it.", "  padded \u00e9\u4e2d\U0001f600  ", "ctrl\u001cchar", "\u001c"])
def test_style_reaches_provider_unmodified(tmp_path, style):
    rec = Recorder()
    code, err = run(tmp_path, rec, instruction=style)
    assert code == 0
    assert [c.style for c in rec.calls] == [style] * 3
    assert [c.body for c in rec.calls] == ["body 1", "body 2", "body 3"]


@pytest.mark.parametrize("blank", ["", " ", "\t\n", "\u3000\u2003"])
def test_explicit_blank_instruction_fails_without_io(tmp_path, blank):
    # Second line of defence for direct run_synth callers; the CLI exits 2 earlier (argparse).
    rec = Recorder()
    code, err = run(tmp_path, rec, instruction=blank)
    assert code == 1
    assert err.startswith(PREFIX + "FAIL ")
    assert len(err.splitlines()) == 1
    assert rec.envs == [] and rec.calls == []
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("model", ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"])
def test_factory_gets_model_once_after_preflight(tmp_path, monkeypatch, model):
    results = preflight_spy(monkeypatch)
    rec = Recorder()
    code, err = run(tmp_path, rec, model=model)
    assert code == 0, err
    assert len(results) == 1 and rec.models == [model] and len(rec.envs) == 1
    assert len(rec.calls) == 3


@pytest.mark.parametrize("model", ["", "Gemini-3.8-Flash-TTS", "gemini-3.8-flash-tts "])
def test_bad_model_fails_before_factory_provider_and_writes(tmp_path, capsys, model):
    rec = Recorder()
    code, err = run(tmp_path, rec, model=model)
    assert code == 1
    assert err == (
        PREFIX + "FAIL model must be one of gemini-3.8-flash-tts, gemini-3.8-flash-lite-tts, eleven_flash_v2_5, eleven_v4\n"
    )
    assert rec.envs == [] and rec.models == [] and rec.calls == []
    assert not (tmp_path / "out").exists()
    assert capsys.readouterr().out == ""
    # positive control: a good model reaches the factory
    code, _ = run(tmp_path, rec)
    assert code == 0 and len(rec.envs) == 1


@pytest.mark.parametrize("model", ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"])
def test_voice_beyond_original_two_and_both_models_end_to_end(tmp_path, model):
    rec = Recorder()
    code, err = run(tmp_path, rec, voice="Zubenelgenubi", model=model)
    assert code == 0, err
    assert rec.models == [model]
    assert [c.voice for c in rec.calls] == ["Zubenelgenubi"] * 3
    assert wavs(tmp_path) == ["001.wav", "002.wav", "003.wav"]
