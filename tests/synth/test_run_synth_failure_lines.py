"""run_synth failure text: one prefixed line per failure, and the API key redacted wherever it came from."""

import io
import json
import sys

import pytest
from run_synth_helper import AUDIO, ENV, KEY, PREFIX, Recorder, run

from scenevoice.synth import ProviderError, run_synth

WORDS = ["alpha", "bravo", "charlie", "delta"]


def run_failing(tmp_path, message, where):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"scenes": [{"ordinal": 1, "title": "t", "body": "b"}]}))

    def provider(request):
        if where == "provider":
            raise ProviderError(message)
        return AUDIO

    def factory(env, model):
        if where == "factory":
            raise ProviderError(message)
        return provider

    stderr = io.StringIO()
    code = run_synth(
        plan_path=path, stdin=None, process_env=ENV, dotenv_path=tmp_path / "missing.env",
        out_dir=tmp_path / "out", voice="Callirrhoe", model="gemini-3.8-flash-tts",
        language="en-GB", instruction=None, provider_factory=factory, stderr=stderr,
    )  # fmt: skip
    return code, stderr.getvalue()


def assert_one_fail_line(err):
    lines = err.splitlines()
    assert all(line.startswith(PREFIX) for line in lines)
    assert sum(1 for line in lines if line.startswith(PREFIX + "FAIL ")) == 1
    assert err.endswith("\n") and not err.endswith("\n\n") and "\r" not in err


@pytest.mark.parametrize("where", ["provider", "factory"])
@pytest.mark.parametrize("sep", ["\r\n", "\n\n\r\n"])
def test_multiline_provider_error_is_one_prefixed_line(tmp_path, where, sep):
    code, err = run_failing(tmp_path, sep.join(WORDS), where)
    assert code == 1
    assert_one_fail_line(err)
    fail_line = next(line for line in err.splitlines() if "FAIL" in line)
    assert all(word in fail_line for word in WORDS)


@pytest.mark.parametrize("where", ["provider", "factory"])
@pytest.mark.parametrize("key_form", ["  " + KEY + "\r\n"])
def test_key_in_a_multiline_message_is_redacted(tmp_path, where, key_form):
    code, err = run_failing(tmp_path, f"first {key_form}second\r\nthird {key_form}", where)
    assert code == 1
    assert_one_fail_line(err)
    assert KEY not in err and "[redacted]" in err
    assert all(word in err for word in ("first", "second", "third"))


def leaky(n=0):
    raise ProviderError(f"boom {KEY}\n and {KEY} end")


@pytest.mark.parametrize("where", ["provider", "factory"])
def test_key_resolved_from_dotenv_only_is_redacted(tmp_path, capsys, where):
    dotenv = tmp_path / ".env"
    dotenv.write_text(f"GOOGLE_CLOUD_PROJECT=p\nGOOGLE_CLOUD_LOCATION=l\nVERTEX_AUTHORIZATION_KEY={KEY}\n")
    rec = Recorder(provider=leaky) if where == "provider" else Recorder(factory_error=ProviderError(f"boom {KEY}"))
    code, err = run(tmp_path, rec, env={}, dotenv_path=dotenv)
    assert code == 1 and "boom" in err and KEY not in err
    assert capsys.readouterr().out == ""


def test_process_env_key_is_redacted_from_a_provider_error(tmp_path, capsys):
    code, err = run(tmp_path, Recorder(provider=leaky), env={**ENV, "VERTEX_AUTHORIZATION_KEY": KEY + "\n"})
    assert code == 1 and "boom" in err and KEY not in err
    assert capsys.readouterr().out == ""


def test_process_env_key_is_redacted_from_a_preflight_failure(tmp_path, monkeypatch):
    calls = []

    def leaking(*args, **kwargs):
        calls.append(1)
        return f"leak {KEY}\n tail"

    monkeypatch.setattr(sys.modules["scenevoice.synth.run_synth"], "run_preflight", leaking)
    code, err = run(tmp_path, Recorder(), env={**ENV, "VERTEX_AUTHORIZATION_KEY": KEY + "\n"})
    assert calls == [1] and code == 1
    assert "leak" in err and KEY not in err
