import io
import json

import pytest
from wav_helper import wav_audio

from scenevoice.synth import ProviderError, run_synth

KEY = "SeCrEt-key-0123456789"
ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": KEY,
}
AUDIO = wav_audio()
PREFIX = "scenevoice synth: "
WORDS = ["alpha", "bravo", "charlie", "delta"]


def multiline(sep):
    return sep.join(WORDS)


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
        plan_path=path,
        stdin=None,
        process_env=ENV,
        dotenv_path=tmp_path / "missing.env",
        out_dir=tmp_path / "out",
        voice="Callirrhoe",
        model="gemini-3.8-flash-tts",
        language="en-GB",
        instruction=None,
        provider_factory=factory,
        stderr=stderr,
    )
    return code, stderr.getvalue()


def assert_one_fail_line(err):
    lines = err.splitlines()
    assert all(line.startswith(PREFIX) for line in lines)
    assert sum(1 for line in lines if line.startswith(PREFIX + "FAIL ")) == 1
    assert err.endswith("\n") and not err.endswith("\n\n")
    assert "\r" not in err
    return lines


@pytest.mark.parametrize("where", ["provider", "factory"])
@pytest.mark.parametrize("sep", ["\n", "\r\n", "\r", "\n\n\r\n"])
def test_multiline_provider_error_is_one_prefixed_line(tmp_path, where, sep):
    code, err = run_failing(tmp_path, multiline(sep), where)
    assert code == 1
    assert_one_fail_line(err)
    fail_line = [ln for ln in err.splitlines() if "FAIL" in ln][0]
    for word in WORDS:
        assert word in fail_line


@pytest.mark.parametrize("where", ["provider", "factory"])
@pytest.mark.parametrize("key_form", [KEY + "\n", KEY, "  " + KEY + "\r\n"])
def test_key_in_multiline_message_is_redacted(tmp_path, where, key_form):
    message = f"first {key_form}second\r\nthird {key_form}"
    code, err = run_failing(tmp_path, message, where)
    assert code == 1
    assert_one_fail_line(err)
    assert KEY not in err
    assert "[redacted]" in err
    for word in ["first", "second", "third"]:
        assert word in err
