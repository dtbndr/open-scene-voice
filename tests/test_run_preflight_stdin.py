import io
import json

import pytest

from scenevoice.synth import run_synth
from scenevoice.synth.run_preflight import run_preflight

ENV = {
    "GOOGLE_CLOUD_PROJECT": "proj",
    "GOOGLE_CLOUD_LOCATION": "loc",
    "VERTEX_AUTHORIZATION_KEY": "dummy-key-value",
}


def closed_stream():
    stream = io.StringIO()
    stream.close()
    return stream


class TtyStdin:
    def __init__(self):
        self.buffer_reads = 0

    def isatty(self):
        return True

    @property
    def buffer(self):
        self.buffer_reads += 1
        raise AssertionError("stdin read")


UNREADABLE = [pytest.param(lambda: None, id="none"), pytest.param(closed_stream, id="closed")]


def preflight(tmp_path, stdin, plan_path=None):
    return run_preflight(plan_path, stdin, ENV, tmp_path / "missing.env", tmp_path / "out")


@pytest.mark.parametrize("make", UNREADABLE)
def test_unreadable_stdin_without_plan_returns_message(tmp_path, make):
    result = preflight(tmp_path, make())
    assert result == "no PLAN given and stdin is not readable"
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("make", UNREADABLE)
def test_unreadable_stdin_fails_run_synth_cleanly(tmp_path, make):
    calls = []
    stderr = io.StringIO()
    code = run_synth(
        plan_path=None,
        stdin=make(),
        process_env=ENV,
        dotenv_path=tmp_path / "missing.env",
        out_dir=tmp_path / "out",
        voice="Callirrhoe",
        model="gemini-3.8-flash-tts",
        language="en-GB",
        instruction=None,
        provider_factory=lambda env, model: calls.append(env),
        stderr=stderr,
    )
    assert code == 1
    assert stderr.getvalue() == "scenevoice synth: FAIL no PLAN given and stdin is not readable\n"
    assert calls == []
    assert not (tmp_path / "out").exists()


def test_terminal_stdin_still_fails_at_step_one_without_io(tmp_path):
    stdin = TtyStdin()
    assert preflight(tmp_path, stdin) == "no PLAN given and stdin is a terminal"
    assert stdin.buffer_reads == 0
    assert not (tmp_path / "out").exists()


def test_plan_path_with_none_stdin_does_not_consult_stdin(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"scenes": [{"ordinal": 1, "title": "t", "body": "hello"}]}))
    result = preflight(tmp_path, None, plan_path=plan)
    assert not isinstance(result, str)
