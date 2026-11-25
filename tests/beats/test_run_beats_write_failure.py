"""A failed write after a paid reply prints the (redacted) text on stdout."""

import importlib
import json

import pytest
from beats_run_helper import (
    GOOD,
    PREFIX,
    canonical,
    fail_write,
    replying,
    run,
)
from chat_run_helper import KEY

pytestmark = pytest.mark.usefixtures("no_sockets")


def test_write_failure_after_paid_reply_prints_the_sidecar_on_stdout(tmp_path, monkeypatch):
    fail_write(monkeypatch)
    code, err, out = run(tmp_path, replying(GOOD))
    assert code == 1
    assert err.splitlines() == [
        f"{PREFIX}FAIL could not write {out} (disk full); "
        "the reply was received and may have been charged, so it is printed on stdout instead"
    ]
    assert run.stdout.getvalue() == canonical()
    assert not out.exists()


def test_write_failure_redacts_the_key_on_stdout(tmp_path, monkeypatch):
    fail_write(monkeypatch)
    code, err, _ = run(tmp_path, replying(f"raw {KEY} reply"))
    assert code == 1
    assert run.stdout.getvalue() == "raw [redacted] reply"
    assert KEY not in err


def test_write_passes_command_beats(tmp_path, monkeypatch):
    module = importlib.import_module("scenevoice.beats.run_beats")
    seen = {}

    def spy(path, text, **kw):
        seen.update(kw)
        return "could not write x (disk full)"

    monkeypatch.setattr(module, "write_out_file", spy)
    run(tmp_path, replying(GOOD))
    assert seen == {"command": "beats"}


def test_write_failure_with_a_coverage_problem_says_the_reply_is_not_a_valid_sidecar(
    tmp_path, monkeypatch
):
    fail_write(monkeypatch)
    raw = json.dumps({"scenes": [GOOD["scenes"][0]]})
    code, err, out = run(tmp_path, replying(raw))
    assert code == 1
    assert err.splitlines() == [
        f"{PREFIX}FAIL could not write {out} (disk full); the reply was received and may have "
        "been charged, so it is printed on stdout instead; it is not a valid complete sidecar: "
        "scene 2 is missing from the reply"
    ]
    assert run.stdout.getvalue() == raw


def test_write_failure_with_a_cut_off_reply_says_so(tmp_path, monkeypatch):
    fail_write(monkeypatch)
    raw = json.dumps(GOOD)
    code, err, out = run(tmp_path, replying(raw, finish="length"))
    assert err.splitlines() == [
        f"{PREFIX}FAIL could not write {out} (disk full); the reply was received and may have "
        "been charged, so it is printed on stdout instead; it is not a valid complete sidecar: "
        "the model stopped at its length limit, so the beats may be incomplete"
    ]
    assert run.stdout.getvalue() == raw
