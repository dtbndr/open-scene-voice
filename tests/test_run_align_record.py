"""Run-level tests for check 5a wiring: record routing, lazy key, routing NOTEs, OK line (D8-D10, D13)."""

import hashlib
import io
import json
import os
from pathlib import Path

import pytest
from align_run_helper import (
    ENV,
    HELLO,
    KEY,
    PREFIX,
    Fake,
    NoTerminal,
    body,
    fail_with,
    go,
    pack_dir,
)
from record_helper import eleven_entry, gemini_entry, write_record

from scenevoice.align.run_align import run_align

FIXTURE = Path(__file__).parent / "fixtures" / "line_timings_record_example.json"
BODIES = ["Welcome back. Today we start.", "Keep it simple. See you next time."]
RUN_NOTE = PREFIX + "NOTE no synth_record.json, all scenes transcribed\n"
SCENE2_NOTE = PREFIX + "NOTE scene 2 line 2: no match, start_ms null\n"
F_NOTE = PREFIX + "NOTE scene 2: alignment text differs from plan body, transcribed\n"
SCENE1 = [
    (" Welcome", 0.23999999865889549),
    (" back.", 0.62),
    (" Today", 1.2344),
    (" we", 1.6),
    (" start.", 1.86),
]
SCENE2 = [
    (" Keep", 0.12),
    (" it", 0.3),
    (" simple.", 0.5),
    (" Sue", 1.9),
    (" you", 2.1),
    (" nexus.", 2.4),
]
SCENE2_FULL = [
    (" Keep", 0.12),
    (" it", 0.3),
    (" simple.", 0.5),
    (" See", 1.5),
    (" you", 1.6),
    (" next", 1.7),
    (" time.", 1.8),
]


def _alignment(text, starts_at):
    """Alignment of one element per character; the start is the latest override at or before it."""
    starts, current = [], 0.0
    for i in range(len(text)):
        current = starts_at.get(i, current)
        starts.append(current)
    return {
        "characters": list(text),
        "character_start_times_seconds": starts,
        "character_end_times_seconds": [s + 0.01 for s in starts],
    }


def _record_entries(wavs, texts, starts):
    return [
        eleven_entry(n, wav, text, alignment=_alignment(text, at))
        for n, (wav, text, at) in enumerate(zip(wavs, texts, starts, strict=True), 1)
    ]


def _worked_record(out, wavs):
    starts = [{0: 0.24, 14: 1.2344}, {0: 0.12, 16: 1.5}]
    return write_record(out, *_record_entries(wavs, BODIES, starts))


def _fail_if_called(key):
    raise AssertionError("the factory must not be called")


def test_record_path_worked_example(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    record = _worked_record(out, wavs)
    record_bytes = record.read_bytes()
    err = io.StringIO()
    code = run_align(
        plan_path, NoTerminal(), {}, tmp_path / "no.env", out, _fail_if_called, err
    )
    assert code == 0
    assert err.getvalue() == (
        PREFIX + "OK 2 scenes, 4 lines, 0 unmatched, 2 from synth record, 0 transcribed\n"
    )
    expected = FIXTURE.read_text(encoding="utf-8")
    expected = expected.replace("1" * 64, hashlib.sha256(wavs[0]).hexdigest())
    expected = expected.replace("2" * 64, hashlib.sha256(wavs[1]).hexdigest())
    assert (out / "line_timings.json").read_bytes() == expected.encode("utf-8")
    assert record.read_bytes() == record_bytes
    assert sorted(p.name for p in out.iterdir()) == [
        "audio",
        "line_timings.json",
        "synth_record.json",
    ]


def test_all_record_run_never_reads_the_dotenv(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    _worked_record(out, wavs)
    dotenv = tmp_path / "dotenv-dir"
    dotenv.mkdir()
    err = io.StringIO()
    code = run_align(plan_path, NoTerminal(), {}, dotenv, out, _fail_if_called, err)
    assert code == 0
    assert err.getvalue().endswith("2 from synth record, 0 transcribed\n")


def test_note_interleaving_in_an_elevenlabs_pack(tmp_path):
    """Mutation: hoisting every (f) NOTE before all line NOTEs puts the scene 2 (f) NOTE first."""
    texts = ["Hello. ...", "Hello there. Mango."]
    plan_path, out, wavs = pack_dir(tmp_path, texts)
    write_record(
        out,
        eleven_entry(1, wavs[0], texts[0], alignment=_alignment(texts[0], {0: 0.2})),
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


def test_f_variant_needs_the_key_and_makes_one_call(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    write_record(
        out,
        *_record_entries(wavs[:1], BODIES[:1], [{0: 0.24, 14: 1.2344}]),
        eleven_entry(2, wavs[1], "Keep it simple. See you next time. [laughs]"),
    )
    fake = Fake([body(SCENE2_FULL)])
    code, err, keys = go(plan_path, out, fake, tmp_path)
    assert code == 0
    assert (len(fake.received), fake.received[0], keys) == (1, wavs[1], [KEY])
    assert err == (
        F_NOTE
        + PREFIX + "OK 2 scenes, 4 lines, 0 unmatched, 1 from synth record, 1 transcribed\n"
    )


def test_f_variant_without_the_key_fails_before_any_call(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    write_record(
        out,
        *_record_entries(wavs[:1], BODIES[:1], [{0: 0.24, 14: 1.2344}]),
        eleven_entry(2, wavs[1], "different"),
    )
    fake = Fake([body(SCENE2_FULL)])
    code, err, keys = go(plan_path, out, fake, tmp_path, env={})
    assert code == 1
    assert err.startswith(PREFIX + "FAIL ") and "OPENROUTER_API_KEY" in err
    assert err.count("\n") == 1
    assert fake.received == [] and keys == []
    assert not (out / "line_timings.json").exists()


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


def test_gemini_pack_with_an_empty_record_transcribes_every_scene_without_a_note(tmp_path):
    texts = ["Hello there.", "Hello there.", "Hello there."]
    plan_path, out, _ = pack_dir(tmp_path, texts)
    write_record(out)
    fake = Fake([body(HELLO)] * 3)
    code, err, keys = go(plan_path, out, fake, tmp_path)
    assert code == 0
    assert len(fake.received) == 3 and keys == [KEY]
    assert err == PREFIX + "OK 3 scenes, 3 lines, 0 unmatched, 0 from synth record, 3 transcribed\n"


def test_gemini_entries_transcribe_every_scene_without_a_routing_note(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, ["Hello there.", "Hello there."])
    write_record(out, gemini_entry(1, wavs[0]), gemini_entry(2, wavs[1]))
    fake = Fake([body(HELLO)] * 2)
    code, err, _ = go(plan_path, out, fake, tmp_path)
    assert code == 0 and len(fake.received) == 2
    assert err == PREFIX + "OK 2 scenes, 2 lines, 0 unmatched, 0 from synth record, 2 transcribed\n"


def test_record_path_zero_token_sentence_is_unmatched_with_a_line_note(tmp_path):
    texts = ["Hello. ..."]
    plan_path, out, wavs = pack_dir(tmp_path, texts)
    write_record(out, eleven_entry(1, wavs[0], texts[0]))
    code, err, keys = go(plan_path, out, Fake([]), tmp_path, env={})
    assert code == 0 and keys == []
    assert err == (
        PREFIX + "NOTE scene 1 line 2: no match, start_ms null\n"
        + PREFIX + "OK 1 scenes, 2 lines, 1 unmatched, 1 from synth record, 0 transcribed\n"
    )
    data = json.loads((out / "line_timings.json").read_text())
    assert data["scenes"][0]["lines"][1] == {"text": "...", "start_ms": None}


def test_check_7_failure_prints_no_f_note(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    write_record(
        out,
        *_record_entries(wavs[:1], BODIES[:1], [{0: 0.24}]),
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
        eleven_entry(1, wavs[0], "Hello. ...", alignment=_alignment("Hello. ...", {0: 0.2})),
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
