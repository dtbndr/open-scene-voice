import hashlib
import json
import os
import sys

import pytest
from test_run_synth_scene import PREFIX, Rec, run
from wav_helper import make_wav

from scenevoice.synth import ProviderAudio

MALFORMED = (
    PREFIX + "FAIL synth_record.json is not a valid synth record "
    "(delete it to regenerate without a settings check)"
)
NO_RECORD = (
    PREFIX + "NOTE no settings recorded for scene 2 (synth_record.json is missing); "
    "settings not checked"
)
NO_ENTRY = (
    PREFIX + "NOTE no settings recorded for scene 2 in synth_record.json; settings not checked"
)


def varying():
    counter = iter(range(10, 1000))
    return Rec(impl=lambda: ProviderAudio("audio/wav", make_wav(next(counter))))


def full_run(tmp_path):
    code, _ = run(tmp_path, varying(), scene=None)
    assert code == 0
    return tmp_path / "out"


def record(out):
    return json.loads((out / "synth_record.json").read_text())["scenes"]


def test_scene_after_full_run_same_settings_updates_only_entry_two(tmp_path, capsys):
    out = full_run(tmp_path)
    capsys.readouterr()
    before = record(out)
    rec = varying()
    code, err = run(tmp_path, rec, scene=2)
    assert code == 0 and rec.factory_calls == 1 and len(rec.calls) == 1
    assert "NOTE" not in err
    after = record(out)
    wav = (out / "audio" / "002.wav").read_bytes()
    assert after[1]["sha256"] == hashlib.sha256(wav).hexdigest() != before[1]["sha256"]
    assert after[0] == before[0] and after[2] == before[2]
    assert after[1] == {**before[1], "sha256": after[1]["sha256"]}
    assert capsys.readouterr().out == ""


def test_voice_mismatch_refused_with_nothing_changed(tmp_path, capsys):
    out = full_run(tmp_path)
    wav, rec_bytes = (out / "audio" / "002.wav").read_bytes(), (out / "synth_record.json").read_bytes()
    rec = varying()
    code, err = run(tmp_path, rec, scene=2, voice="Charon")
    assert code == 1
    assert err == (
        PREFIX + 'FAIL scene 2 settings differ from synth_record.json: '
        'voice recorded "Callirrhoe", passed "Charon"\n'
    )
    assert rec.factory_calls == 0
    assert (out / "audio" / "002.wav").read_bytes() == wav
    assert (out / "synth_record.json").read_bytes() == rec_bytes
    assert capsys.readouterr().out == ""


def test_malformed_record_refused_before_any_call(tmp_path, capsys):
    out = full_run(tmp_path)
    (out / "synth_record.json").write_bytes(b"not json")
    rec = varying()
    code, err = run(tmp_path, rec, scene=2)
    assert code == 1 and err == MALFORMED + "\n"
    assert rec.factory_calls == 0
    assert (out / "synth_record.json").read_bytes() == b"not json"
    assert capsys.readouterr().out == ""


def test_no_record_notes_first_then_creates_record_with_entry_two(tmp_path, capsys):
    out = full_run(tmp_path)
    (out / "synth_record.json").unlink()
    code, err = run(tmp_path, varying(), scene=2)
    assert code == 0
    assert err.splitlines()[0] == NO_RECORD
    assert err.count("NOTE") == 1
    assert [e["ordinal"] for e in record(out)] == [2]
    assert capsys.readouterr().out == ""


def test_record_without_entry_two_gets_it_inserted_between(tmp_path, capsys):
    out = full_run(tmp_path)
    entries = record(out)
    (out / "synth_record.json").write_text(
        json.dumps({"scenes": [entries[0], entries[2]]})
    )
    code, err = run(tmp_path, varying(), scene=2)
    assert code == 0
    assert err.splitlines()[0] == NO_ENTRY
    after = record(out)
    assert [e["ordinal"] for e in after] == [1, 2, 3]
    assert after[0] == entries[0] and after[2] == entries[2]
    assert capsys.readouterr().out == ""


def test_record_write_failure_keeps_new_wav_and_old_record(tmp_path, monkeypatch, capsys):
    out = full_run(tmp_path)
    old_wav, old_record = (out / "audio" / "002.wav").read_bytes(), (out / "synth_record.json").read_bytes()
    calls = []

    def fake(directory, data):
        calls.append(data)
        return "could not write synth_record.json"

    monkeypatch.setattr(sys.modules["scenevoice.synth.make_record_hook"], "write_record_file", fake)
    code, err = run(tmp_path, varying(), scene=2)
    assert len(calls) == 1  # positive control
    assert code == 1
    assert err.splitlines()[-1] == PREFIX + "FAIL scene 2: could not write synth_record.json"
    assert (out / "audio" / "002.wav").read_bytes() != old_wav
    assert (out / "synth_record.json").read_bytes() == old_record
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("mode", ["malformed", "mode000"])
def test_full_run_never_reads_the_record(tmp_path, monkeypatch, capsys, mode):
    if mode == "mode000" and os.geteuid() == 0:
        pytest.skip("root ignores modes")
    out = tmp_path / "out"
    out.mkdir()
    target = out / "synth_record.json"
    target.write_bytes(b"not json")
    if mode == "mode000":
        target.chmod(0)
    reads = []
    module = sys.modules["scenevoice.synth.run_preflight"]
    real = module.load_record
    monkeypatch.setattr(module, "load_record", lambda d: reads.append(d) or real(d))
    try:
        code, _ = run(tmp_path, varying(), scene=None)
    finally:
        if target.exists():
            target.chmod(0o644)
    assert code == 0 and reads == []
    assert len(record(out)) == 3
    assert capsys.readouterr().out == ""


def test_load_record_spy_is_called_on_scene_run(tmp_path, monkeypatch):
    out = full_run(tmp_path)
    reads = []
    module = sys.modules["scenevoice.synth.run_preflight"]
    real = module.load_record
    monkeypatch.setattr(module, "load_record", lambda d: reads.append(d) or real(d))
    code, _ = run(tmp_path, varying(), scene=2)
    assert code == 0 and len(reads) == 1
    assert out.exists()


def test_missing_env_fails_before_any_record_check(tmp_path, capsys):
    out = full_run(tmp_path)
    (out / "synth_record.json").write_bytes(b"not json")
    code, err = run(tmp_path, varying(), scene=2, env={})
    assert code == 1 and "missing environment variables" in err
    assert "synth_record" not in err
    assert capsys.readouterr().out == ""
