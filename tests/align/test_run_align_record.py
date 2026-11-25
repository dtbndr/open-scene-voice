"""Run-level tests for check 5a wiring: record routing, lazy key and dotenv, f-variant, OK line (D8-D10, D13)."""

import hashlib
import io
import json

from align_run_helper import (
    BODIES,
    F_NOTE,
    HELLO,
    KEY,
    PREFIX,
    SCENE2_FULL,
    Fake,
    NoTerminal,
    body,
    fail_if_called,
    go,
    pack_dir,
    record_entries,
    worked_record,
)
from paths_helper import FIXTURES
from record_helper import eleven_entry, gemini_entry, write_record

from scenevoice.align.run_align import run_align
from scenevoice.cli.main import main

FIXTURE = FIXTURES / "line_timings_record_example.json"


def test_record_path_worked_example(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    record = worked_record(out, wavs)
    record_bytes = record.read_bytes()
    err = io.StringIO()
    code = run_align(
        plan_path, NoTerminal(), {}, tmp_path / "no.env", out, fail_if_called, err
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
    worked_record(out, wavs)
    dotenv = tmp_path / "dotenv-dir"
    dotenv.mkdir()
    err = io.StringIO()
    code = run_align(plan_path, NoTerminal(), {}, dotenv, out, fail_if_called, err)
    assert code == 0
    assert err.getvalue().endswith("2 from synth record, 0 transcribed\n")


def test_all_record_run_never_reads_the_key_file(tmp_path):
    """Check 5a: like ./.env, the key file is read only when some scene needs transcription."""
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    worked_record(out, wavs)
    key_file = tmp_path / "keys.env"
    key_file.write_text("this is not a binding\n", encoding="utf-8")
    key_file.chmod(0o644)
    err = io.StringIO()
    code = run_align(
        plan_path, NoTerminal(), {}, tmp_path / "no.env", out, fail_if_called, err,
        key_file_path=key_file,
    )  # fmt: skip
    assert code == 0
    assert "FAIL" not in err.getvalue() and "key file" not in err.getvalue()
    assert err.getvalue().endswith("2 from synth record, 0 transcribed\n")


def test_all_record_run_through_main_never_reads_the_key_file(tmp_path, monkeypatch, capsys):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    worked_record(out, wavs)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("sys.stdin", NoTerminal())
    key_file = tmp_path / "keys.env"
    key_file.write_text("this is not a binding\n", encoding="utf-8")
    key_file.chmod(0o644)
    monkeypatch.setenv("SCENEVOICE_KEYS_FILE", str(key_file))
    code = main(["align", str(plan_path), str(out)], transcriber_factory=fail_if_called)
    err = capsys.readouterr().err
    assert code == 0
    assert "FAIL" not in err and "key file" not in err


def test_f_variant_needs_the_key_and_makes_one_call(tmp_path):
    plan_path, out, wavs = pack_dir(tmp_path, BODIES)
    write_record(
        out,
        *record_entries(wavs[:1], BODIES[:1], [{0: 0.24, 14: 1.2344}]),
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
        *record_entries(wavs[:1], BODIES[:1], [{0: 0.24, 14: 1.2344}]),
        eleven_entry(2, wavs[1], "different"),
    )
    fake = Fake([body(SCENE2_FULL)])
    code, err, keys = go(plan_path, out, fake, tmp_path, env={})
    assert code == 1
    assert err.startswith(PREFIX + "FAIL ") and "OPENROUTER_API_KEY" in err
    assert err.count("\n") == 1
    assert fake.received == [] and keys == []
    assert not (out / "line_timings.json").exists()


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
