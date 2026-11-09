import hashlib
import json
import sys

from wav_helper import make_wav

from scenevoice.synth import Alignment, ProviderAudio, RecordEntry, RecordSettings
from scenevoice.synth.make_record_hook import make_record_hook

SETTINGS = RecordSettings("Kore", "gemini-3.8-flash-tts", "en-GB", None)


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
