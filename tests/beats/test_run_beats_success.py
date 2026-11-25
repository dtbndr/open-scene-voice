"""A valid reply: the canonical sidecar, one OK line, the request and the stderr shape."""

import hashlib
import json

import pytest
from beats_run_helper import (
    GOOD,
    PREFIX,
    SCRIPT,
    canonical,
    replying,
    run,
)
from chat_run_helper import KEY

from scenevoice.beats import check_sidecar_shape

pytestmark = pytest.mark.usefixtures("no_sockets")


def test_valid_reply_writes_canonical_sidecar_and_one_ok_line(tmp_path, capsys):
    fake = replying(GOOD)
    code, err, out = run(tmp_path, fake)
    assert code == 0
    assert err.splitlines() == [f"{PREFIX}OK {out} (2 scenes, 2 beats)"]
    assert out.read_bytes() == canonical().encode("utf-8")
    assert check_sidecar_shape(json.loads(out.read_text())) is None
    assert run.stdout.getvalue() == "" and capsys.readouterr().out == ""
    assert fake.keys == [KEY] and len(fake.requests) == 1


def test_hash_is_sha256_of_script_bytes_and_script_is_untouched(tmp_path):
    code, _, out = run(tmp_path, replying(GOOD))
    assert code == 0
    assert json.loads(out.read_text())["script_sha256"] == hashlib.sha256(SCRIPT).hexdigest()
    assert run.script_path.read_bytes() == SCRIPT


def test_fenced_reply_is_cleaned_with_a_note_and_written_canonical(tmp_path):
    fenced = "```json\n" + json.dumps(GOOD) + "\n```\n"
    code, err, out = run(tmp_path, replying(fenced))
    assert code == 0
    lines = err.splitlines()
    assert lines[0].startswith(PREFIX + "NOTE cleaned: ")
    assert "code fence" in lines[0]
    assert lines[1] == f"{PREFIX}OK {out} (2 scenes, 2 beats)"
    assert out.read_bytes() == canonical().encode("utf-8")


def test_request_carries_the_model_and_the_scene_segments(tmp_path):
    fake = replying(GOOD)
    run(tmp_path, fake)
    request = json.loads(fake.requests[0])
    assert request["model"] == "synthetic/model"
    prompt = "\n".join(m["content"] for m in request["messages"])
    assert "First one." in prompt and "Third one." in prompt


def test_every_stderr_line_has_the_prefix_and_stdout_is_empty(tmp_path, capsys):
    cases = {
        "ok": replying(GOOD),
        "fenced": replying("```\n" + json.dumps(GOOD) + "\n```"),
        "bad": replying("nope"),
        "cut": replying(json.dumps(GOOD), finish="length"),
    }
    for name, fake in cases.items():
        folder = tmp_path / name
        folder.mkdir()
        _, err, _ = run(folder, fake)
        assert err and all(line.startswith(PREFIX) for line in err.splitlines())
        assert run.stdout.getvalue() == ""
    assert capsys.readouterr().out == ""
