"""synth --scene N on an ElevenLabs directory (D14, D21): offline, injected post, no network."""

import json

import pytest
from elevenlabs_scene_helper import (
    BODIES,
    FLASH,
    PREFIX,
    VOICE,
    FakePost,
    el,
    full_run,
    records,
    setup_env,
    synth,
)

NO_RECORD = (
    PREFIX + "NOTE no settings recorded for scene 2 (synth_record.json is missing); "
    "settings not checked"
)
NO_ENTRY = (
    PREFIX + "NOTE no settings recorded for scene 2 in synth_record.json; settings not checked"
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    return setup_env(tmp_path, monkeypatch)


def test_scene_same_settings_updates_only_entry_two_with_plan_neighbours(env, capsys):
    out = full_run(env, capsys)
    before = records(out)
    old_wav = (out / "audio" / "002.wav").read_bytes()
    post = FakePost("success_v4_overshoot.json")
    code, err = synth(capsys, post, *el(FLASH, VOICE, "--scene", "2"))
    assert code == 0 and "NOTE" not in err
    assert len(post.calls) == 1
    assert post.calls[0]["previous_text"] == BODIES[0]
    assert post.calls[0]["next_text"] == BODIES[2]
    assert (out / "audio" / "002.wav").read_bytes() != old_wav
    after = records(out)
    assert after[1]["sha256"] != before[1]["sha256"]
    assert after[1]["alignment"] != before[1]["alignment"]
    assert after[0] == before[0] and after[2] == before[2]
    assert json.dumps(after[0]) == json.dumps(before[0])
    assert json.dumps(after[2]) == json.dumps(before[2])


def test_carried_over_entries_keep_their_serialized_bytes(env, capsys):
    out = full_run(env, capsys)
    before = (out / "synth_record.json").read_text(encoding="utf-8")
    code, err = synth(capsys, FakePost(), *el(FLASH, VOICE, "--scene", "2"))
    assert code == 0, err
    after = (out / "synth_record.json").read_text(encoding="utf-8")
    for ordinal in (1, 3):
        assert block(before, ordinal) == block(after, ordinal) != ""


def block(text, ordinal):
    """The serialized text of one entry, cut at its ordinal line up to the next ordinal line."""
    marker = f'"ordinal": {ordinal},'
    start = text.find(marker)
    nxt = text.find('"ordinal":', start + 1)
    return text[start:nxt if nxt != -1 else len(text)]


def test_last_scene_sends_previous_text_and_no_next_text(env, capsys):
    full_run(env, capsys)
    post = FakePost()
    code, err = synth(capsys, post, *el(FLASH, VOICE, "--scene", "3"))
    assert code == 0, err
    assert post.calls[0]["previous_text"] == BODIES[1]
    assert "next_text" not in post.calls[0]


def test_missing_record_gives_note_and_writes_entry_two_with_alignment(env, capsys):
    out = full_run(env, capsys)
    (out / "synth_record.json").unlink()
    code, err = synth(capsys, FakePost(), *el(FLASH, VOICE, "--scene", "2"))
    assert code == 0 and err.splitlines()[0] == NO_RECORD
    entries = records(out)
    assert [e["ordinal"] for e in entries] == [2]
    assert entries[0]["alignment"]["characters"] and entries[0]["language"] is None


def test_record_without_entry_two_inserts_it_between_one_and_three(env, capsys):
    out = full_run(env, capsys)
    data = json.loads((out / "synth_record.json").read_text())
    kept = [data["scenes"][0], data["scenes"][2]]
    (out / "synth_record.json").write_text(json.dumps({"scenes": kept}))
    code, err = synth(capsys, FakePost(), *el(FLASH, VOICE, "--scene", "2"))
    assert code == 0 and err.splitlines()[0] == NO_ENTRY
    after = records(out)
    assert [e["ordinal"] for e in after] == [1, 2, 3]
    assert after[0] == kept[0] and after[2] == kept[1]


def test_unencodable_alignment_character_keeps_wav_and_old_record(env, capsys):
    out = full_run(env, capsys, "success_v4_overshoot.json")
    old_wav = (out / "audio" / "002.wav").read_bytes()
    rec = (out / "synth_record.json").read_bytes()
    post = FakePost("lone_surrogate_character.json")
    code, err = synth(capsys, post, *el(FLASH, VOICE, "--scene", "2"))
    assert code == 1
    assert err.strip().splitlines()[-1] == PREFIX + "FAIL scene 2: could not write synth_record.json"
    assert (out / "audio" / "002.wav").read_bytes() != old_wav
    assert (out / "synth_record.json").read_bytes() == rec
