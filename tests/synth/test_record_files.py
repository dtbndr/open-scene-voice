"""Record hook: entries, seeding, write failures (D21: an unencodable alignment character is a write failure)."""

import hashlib
import json
import os
import sys
import wave

import paths_helper
from wav_helper import make_wav

from scenevoice.cli.main import main
from scenevoice.synth import (
    Alignment,
    ProviderAudio,
    RecordEntry,
    RecordSettings,
    make_elevenlabs_provider,
)
from scenevoice.synth.make_record_hook import make_record_hook
from scenevoice.synth.record_name import RECORD_NAME
from scenevoice.synth.regen_notes import missing_entry_note, missing_record_note
from scenevoice.synth.serialize_record import serialize_record
from scenevoice.synth.settings_mismatch import settings_mismatch
from scenevoice.synth.write_record_file import write_record_file

FIXTURE = paths_helper.FIXTURES / "synth_record_contract_example.json"


ALIGNMENT = Alignment(("H", "i", "."), (0.0, 0.08, 0.16), (0.08, 0.16, 0.2))


def _entry(**overrides):
    fields = dict(
        ordinal=1,
        sha256="a" * 64,
        voice="Algenib",
        model="gemini-3.8-flash-tts",
        language="en-GB",
        instruction=None,
        alignment=None,
    )
    fields.update(overrides)
    return RecordEntry(**fields)


def _contract_entries():
    return [
        _entry(),
        _entry(
            ordinal=2,
            sha256="b" * 64,
            voice="EXAVITQu4vr4xnSDxMaL",
            model="eleven_flash_v2_5",
            language=None,
            alignment=ALIGNMENT,
        ),
    ]


def test_record_name():
    assert RECORD_NAME == "synth_record.json"


def test_contract_example_bytes_match_fixture():
    assert serialize_record(_contract_entries()) == FIXTURE.read_bytes()


def test_empty_record_bytes():
    assert serialize_record([]) == b'{\n  "scenes": []\n}\n'


DATA = b'{\n  "scenes": []\n}\n'


MESSAGE = "could not write synth_record.json"


def _module():
    return sys.modules["scenevoice.synth.write_record_file"]


def test_creates_file_with_exact_bytes(tmp_path):
    assert write_record_file(tmp_path, DATA) is None
    assert os.listdir(tmp_path) == ["synth_record.json"]
    assert (tmp_path / "synth_record.json").read_bytes() == DATA


def test_replaces_existing_regular_file(tmp_path):
    (tmp_path / "synth_record.json").write_bytes(b"old")
    assert write_record_file(tmp_path, DATA) is None
    assert (tmp_path / "synth_record.json").read_bytes() == DATA
    assert os.listdir(tmp_path) == ["synth_record.json"]


def test_rename_failure_keeps_old_file_and_leaves_no_temp(tmp_path, monkeypatch):
    target = tmp_path / "synth_record.json"
    target.write_bytes(b"old")
    calls = []

    def fake_replace(src, dst):
        calls.append(src)
        raise OSError("boom")

    monkeypatch.setattr(_module().os, "replace", fake_replace)
    assert write_record_file(tmp_path, DATA) == MESSAGE
    assert calls  # positive control: the fake was reached
    assert target.read_bytes() == b"old"
    assert os.listdir(tmp_path) == ["synth_record.json"]


def test_missing_directory_returns_message_not_raises(tmp_path):
    assert write_record_file(tmp_path / "absent", DATA) == MESSAGE


HEAD = "scene 2 settings differ from synth_record.json: "


def entry(voice="V", model="M", language="en-GB", instruction=None):
    return RecordEntry(2, "0" * 64, voice, model, language, instruction, None)


def passed(voice="V", model="M", language="en-GB", instruction=None):
    return RecordSettings(voice, model, language, instruction)


def test_all_equal_is_none():
    assert settings_mismatch(2, entry(instruction="calm"), passed(instruction="calm")) is None


def test_voice_only():
    got = settings_mismatch(2, entry(voice="Callirrhoe"), passed(voice="Charon"))
    assert got == HEAD + 'voice recorded "Callirrhoe", passed "Charon"'


def test_all_four_in_order():
    got = settings_mismatch(
        2,
        entry("A", "C", "en-GB", "x"),
        passed("B", "D", "en-US", "y"),
    )
    assert got == HEAD + (
        'voice recorded "A", passed "B"; model recorded "C", passed "D"; '
        'language recorded "en-GB", passed "en-US"; instruction recorded "x", passed "y"'
    )


def test_instruction_recorded_none():
    got = settings_mismatch(2, entry(), passed(instruction="calm"))
    assert got == HEAD + 'instruction recorded (none), passed "calm"'


def test_literal_none_text_stays_distinct():
    got = settings_mismatch(2, entry(instruction="(none)"), passed())
    assert got == HEAD + 'instruction recorded "(none)", passed (none)'


def test_line_break_runs_collapse_to_one_space():
    got = settings_mismatch(2, entry(instruction="a\r\nb\n\nc"), passed(instruction="z"))
    assert got == HEAD + 'instruction recorded "a b c", passed "z"'


def test_note_texts():
    assert missing_record_note(2) == (
        "no settings recorded for scene 2 (synth_record.json is missing); settings not checked"
    )
    assert missing_entry_note(2) == (
        "no settings recorded for scene 2 in synth_record.json; settings not checked"
    )


SETTINGS = RecordSettings("Kore", "gemini-3.8-flash-tts", "en-GB", None)


EL_FIXTURES = paths_helper.FIXTURES / "elevenlabs"


def read(tmp_path):
    return json.loads((tmp_path / "synth_record.json").read_text())["scenes"]


def seed(n, sha="aa"):
    return RecordEntry(n, sha, "V", "M", None, "seed", None)


def test_two_scenes_in_order_with_hashes_and_settings(tmp_path):
    hook = make_record_hook(tmp_path, SETTINGS, [])
    wav1, wav2 = make_wav(5), make_wav(9)
    assert hook(1, ProviderAudio("audio/wav", wav1)) is None
    assert hook(2, ProviderAudio("audio/wav", wav2)) is None
    scenes = read(tmp_path)
    assert [s["ordinal"] for s in scenes] == [1, 2]
    assert [s["sha256"] for s in scenes] == [hashlib.sha256(w).hexdigest() for w in (wav1, wav2)]
    for s in scenes:
        assert (s["voice"], s["model"], s["language"], s["instruction"], s["alignment"]) == (
            "Kore", "gemini-3.8-flash-tts", "en-GB", None, None)


def test_alignment_written_as_object(tmp_path):
    al = Alignment(("a", "b"), (0.0, 0.08), (0.08, 0.16))
    hook = make_record_hook(tmp_path, SETTINGS, [])
    assert hook(1, ProviderAudio("audio/wav", make_wav(5), al)) is None
    assert read(tmp_path)[0]["alignment"] == {
        "characters": ["a", "b"],
        "character_start_times_seconds": [0.0, 0.08],
        "character_end_times_seconds": [0.08, 0.16],
    }


def test_seeded_entries_insert_and_replace(tmp_path):
    hook = make_record_hook(tmp_path, SETTINGS, [seed(1), seed(3)])
    wav = make_wav(5)
    assert hook(2, ProviderAudio("audio/wav", wav)) is None
    scenes = read(tmp_path)
    assert [s["ordinal"] for s in scenes] == [1, 2, 3]
    assert scenes[1]["sha256"] == hashlib.sha256(wav).hexdigest()
    assert scenes[0]["instruction"] == "seed" and scenes[2]["instruction"] == "seed"
    assert hook(3, ProviderAudio("audio/wav", wav)) is None
    scenes = read(tmp_path)
    assert [s["ordinal"] for s in scenes] == [1, 2, 3]
    assert scenes[2]["instruction"] is None and scenes[2]["sha256"] == hashlib.sha256(wav).hexdigest()
    assert scenes[0]["instruction"] == "seed" and scenes[1]["instruction"] is None


def test_write_failure_returns_message(tmp_path, monkeypatch):
    calls = []

    def fake(directory, data):
        calls.append(directory)
        return "could not write synth_record.json"

    monkeypatch.setattr(sys.modules["scenevoice.synth.make_record_hook"], "write_record_file", fake)
    hook = make_record_hook(tmp_path, SETTINGS, [])
    assert hook(1, ProviderAudio("audio/wav", make_wav(5))) == "could not write synth_record.json"
    assert calls  # positive control: the fake was called
    assert not (tmp_path / "synth_record.json").exists()


FAILURE = "could not write synth_record.json"


EL_SETTINGS = RecordSettings("EXAVITQu4vr4xnSDxMaL", "eleven_flash_v2_5", None, None)


GOOD = Alignment(("a", "b"), (0.0, 0.08), (0.08, 0.16))


LONE = Alignment(("\ud83d", "t"), (0.0, 0.1), (0.1, 0.2))


def test_full_run_stops_with_the_write_failure_and_no_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "dummy-eleven-key")
    plan = {"scenes": [{"ordinal": i, "title": "t", "body": f"Body {i}."} for i in (1, 2, 3)]}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    names = {2: "lone_surrogate_character.json"}
    calls = []

    def post(url, headers, body, timeout):
        calls.append(url)
        return (EL_FIXTURES / names.get(len(calls), "success_flash.json")).read_bytes()

    out = tmp_path / "out"
    code = main(
        ["synth", "plan.json", "--out", str(out), "--voice", "EXAVITQu4vr4xnSDxMaL",
         "--model", "eleven_flash_v2_5"],
        provider_factory=lambda env, m: make_elevenlabs_provider(env, m, post=post))
    captured = capsys.readouterr()
    assert code == 1 and captured.out == ""
    assert f"scenevoice synth: FAIL scene 2: {FAILURE}" in captured.err
    assert "Traceback" not in captured.err
    for n in (1, 2):
        with wave.open(str(out / "audio" / f"00{n}.wav")) as w:
            assert w.getnframes() == 4800
    assert not (out / "audio" / "003.wav").exists()
    scenes = json.loads((out / "synth_record.json").read_text(encoding="utf-8"))["scenes"]
    assert [s["ordinal"] for s in scenes] == [1]
    assert len(calls) == 2
