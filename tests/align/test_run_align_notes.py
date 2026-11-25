"""Run-level tests for the NOTE lines of a run: routing, run and line NOTE order, and NOTEs before a FAIL."""

import io
import os

import pytest
from align_run_helper import (
    BODIES,
    ENV,
    F_NOTE,
    HELLO,
    KEY,
    PREFIX,
    RUN_NOTE,
    SCENE1,
    SCENE2,
    SCENE2_NOTE,
    Fake,
    NoTerminal,
    alignment_at,
    body,
    fail_with,
    go,
    pack_dir,
    record_entries,
)
from record_helper import eleven_entry, write_record

from scenevoice.align.run_align import run_align


def test_note_interleaving_in_an_elevenlabs_pack(tmp_path):
    """Mutation: hoisting every (f) NOTE before all line NOTEs puts the scene 2 (f) NOTE first."""
    texts = ["Hello. ...", "Hello there. Mango."]
    plan_path, out, wavs = pack_dir(tmp_path, texts)
    write_record(
        out,
        eleven_entry(1, wavs[0], texts[0], alignment=alignment_at(texts[0], {0: 0.2})),
        eleven_entry(2, wavs[1], "other text"),
    )
    fake = Fake([body(HELLO)])
    code, err, keys = go(plan_path, out, fake, tmp_path)
    assert code == 0
    assert fake.received == [wavs[1]]
    assert keys == [KEY]
    assert err == (
        PREFIX + "NOTE scene 1 line 2: no match, start_ms null\n"
        + F_NOTE
        + SCENE2_NOTE
        + PREFIX + "OK 2 scenes, 4 lines, 2 unmatched, 1 from synth record, 1 transcribed\n"
    )


def test_no_record_file_run_note_first_then_line_note_then_ok(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    fake = Fake([body(SCENE1), body(SCENE2)])
    code, err, keys = go(plan_path, out, fake, tmp_path)
    assert code == 0
    assert err == (
        RUN_NOTE
        + SCENE2_NOTE
        + PREFIX + "OK 2 scenes, 4 lines, 1 unmatched, 0 from synth record, 2 transcribed\n"
    )
    assert fake.received == wavs and keys == [KEY]


def test_no_record_run_note_is_written_after_the_last_call(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, BODIES)
    log = []
    responses = [body(SCENE1), body(SCENE2)]

    def transcriber(wav):
        log.append("call")
        return responses[log.count("call") - 1]

    class Err(io.StringIO):
        def write(self, text):
            log.append(text)
            return super().write(text)

    code = run_align(
        plan_path, NoTerminal(), ENV, tmp_path / "no.env", out, lambda k: transcriber, Err()
    )
    assert code == 0
    assert log == [
        "call",
        "call",
        RUN_NOTE,
        SCENE2_NOTE,
        PREFIX + "OK 2 scenes, 4 lines, 1 unmatched, 0 from synth record, 2 transcribed\n",
    ]


def test_check_7_failure_prints_no_f_note(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    write_record(
        out,
        *record_entries(wavs[:1], BODIES[:1], [{0: 0.24}]),
        eleven_entry(2, wavs[1], "different"),
    )
    code, err, _ = go(plan_path, out, Fake([fail_with(503, "down")]), tmp_path)
    assert code == 1
    assert err == f"{PREFIX}FAIL scene 2: provider error (HTTP 503): down\n"


def test_check_7_failure_prints_no_run_note(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, BODIES)
    code, err, _ = go(plan_path, out, Fake([body(SCENE1), fail_with(503, "down")]), tmp_path)
    assert code == 1
    assert err == f"{PREFIX}FAIL scene 2: provider error (HTTP 503): down\n"


def test_check_8_failure_prints_routing_and_line_notes_before_fail(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, ["Hello. ...", "Hello there. Mango."])
    write_record(
        out,
        eleven_entry(1, wavs[0], "Hello. ...", alignment=alignment_at("Hello. ...", {0: 0.2})),
        eleven_entry(2, wavs[1], "other text"),
    )
    fake = Fake([body(HELLO)])
    original = fake.__call__

    def lock_after_last_call(wav):
        result = original(wav)
        os.chmod(out, 0o500)
        return result

    err = io.StringIO()
    try:
        code = run_align(
            plan_path, NoTerminal(), ENV, tmp_path / "no.env", out, lambda k: lock_after_last_call, err
        )
    finally:
        os.chmod(out, 0o700)
    if code == 0:
        pytest.skip("directory permissions are not enforced here")
    assert code == 1
    assert err.getvalue().splitlines() == [
        PREFIX + "NOTE scene 1 line 2: no match, start_ms null",
        F_NOTE.rstrip("\n"),
        SCENE2_NOTE.rstrip("\n"),
        PREFIX + "FAIL could not write line_timings.json",
    ]
