import dataclasses
import io
import json
import sys

from scenevoice.synth import (
    VERTEX,
    PlanScene,
    ProviderError,
    check_limits,
    run_preflight,
    run_synth,
)
from scenevoice.validation import Violation

KEY = "SeCrEt-key-0123456789"
ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": KEY,
}
MODEL = "gemini-3.8-flash-tts"


def scenes(n=1, body="b"):
    return [PlanScene(i, "t", body) for i in range(1, n + 1)]


def plan_bytes(n=1, body="hello"):
    items = [{"ordinal": i, "title": "t", "body": body} for i in range(1, n + 1)]
    return json.dumps({"scenes": items}).encode("utf-8")


class Stdin:
    def __init__(self, data=b""):
        self.buffer = io.BytesIO(data)

    def isatty(self):
        return False


def test_check_limits_count_first_and_fake_not_called():
    calls = []

    def fake(items):
        calls.append(items)
        return None

    result = check_limits(scenes(1000), body_check=fake)
    assert result is not None and "1000 scenes exceeds the maximum of 999" in result.message
    assert calls == []
    assert check_limits(scenes(1), body_check=fake) is None
    assert len(calls) == 1


def test_check_limits_returns_fake_result():
    verdict = Violation("x", "fake says no")
    assert check_limits(scenes(), body_check=lambda items: verdict) is verdict


def test_check_limits_default_is_byte_check():
    result = check_limits(scenes(1, "a" * 8001))
    assert result is not None
    assert result.message == "body over 8000 UTF-8 bytes: scene 1: 8001 bytes"


def test_run_preflight_spec_env_names(tmp_path):
    fake = dataclasses.replace(VERTEX, env_names=("FAKE_KEY",))
    result = run_preflight(
        None, Stdin(plan_bytes()), {}, tmp_path / ".env", tmp_path / "out", spec=fake
    )
    assert result == "missing environment variables: FAKE_KEY"


def test_run_preflight_applies_body_check(tmp_path):
    seen = []

    def fake(items):
        seen.append(items)
        return Violation("x", "stop here")

    result = run_preflight(
        None, Stdin(plan_bytes()), ENV, tmp_path / ".env", tmp_path / "out", body_check=fake
    )
    assert result == "stop here"
    assert len(seen) == 1


def test_run_synth_binds_model_into_body_check(tmp_path, monkeypatch):
    received = []

    def check(items, model):
        received.append((list(items), model))
        return Violation("x", "stop here")

    stand_in = dataclasses.replace(VERTEX, check_body_limit=check)
    module = sys.modules["scenevoice.synth.run_synth"]
    monkeypatch.setattr(module, "provider_for_model", lambda model: stand_in)
    err = io.StringIO()
    code = run_synth(
        None, Stdin(plan_bytes()), ENV, tmp_path / ".env", tmp_path / "out",
        "Charon", MODEL, "en-GB", None, lambda env, model: None, err,
    )  # fmt: skip
    assert code == 1 and err.getvalue() == "scenevoice synth: FAIL stop here\n"
    assert len(received) == 1
    assert received[0][1] == MODEL and received[0][0][0].body == "hello"


def leaky(request):
    raise ProviderError(f"boom {KEY} end")


def test_run_synth_redacts_vertex_key_process_and_resolved(tmp_path):
    for env, dotenv_text in ((ENV, ""), ({}, f"GOOGLE_CLOUD_PROJECT=p\nGOOGLE_CLOUD_LOCATION=l\nVERTEX_AUTHORIZATION_KEY={KEY}\n")):
        dotenv = tmp_path / ".env"
        dotenv.write_text(dotenv_text)
        err = io.StringIO()
        out = tmp_path / ("o" + str(bool(dotenv_text)))
        code = run_synth(
            None, Stdin(plan_bytes()), env, dotenv, out,
            "Charon", MODEL, "en-GB", None, lambda e, m: leaky, err,
        )  # fmt: skip
        assert code == 1 and "boom" in err.getvalue() and KEY not in err.getvalue()
