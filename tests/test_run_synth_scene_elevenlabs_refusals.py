"""synth --scene N refusals on an ElevenLabs directory (D14, D21): offline, injected post, no network."""

import json

import pytest
from elevenlabs_scene_helper import (
    DIFF,
    FLASH,
    MALFORMED,
    V4,
    VOICE,
    el,
    full_run,
    setup_env,
    synth,
    untouched,
)

from scenevoice.synth import ENV_NAMES


@pytest.fixture
def env(tmp_path, monkeypatch):
    return setup_env(tmp_path, monkeypatch)


def test_different_voice_is_refused(env, capsys):
    out = full_run(env, capsys)
    code, err = untouched(out, lambda p: synth(capsys, p, *el(FLASH, "other", "--scene", "2")))
    assert code == 1
    assert err == DIFF + f'voice recorded "{VOICE}", passed "other"\n'


def test_different_model_is_refused(env, capsys):
    out = full_run(env, capsys)
    code, err = untouched(out, lambda p: synth(capsys, p, *el(V4, VOICE, "--scene", "2")))
    assert code == 1
    assert err == DIFF + f'model recorded "{FLASH}", passed "{V4}"\n'


def test_gemini_run_on_elevenlabs_entry_is_refused(env, capsys, monkeypatch):
    out = full_run(env, capsys)
    for name in ENV_NAMES:
        monkeypatch.setenv(name, "vertex-dummy-value")
    code, err = untouched(out, lambda p: synth(
        capsys, p, "--voice", "Charon", "--model", "gemini-3.8-flash-tts", "--scene", "2"))
    assert code == 1
    assert err == DIFF + (
        f'voice recorded "{VOICE}", passed "Charon"; '
        f'model recorded "{FLASH}", passed "gemini-3.8-flash-tts"; '
        'language recorded (none), passed "en-GB"\n')


def test_elevenlabs_run_on_gemini_entry_is_refused(env, capsys, monkeypatch):
    out = env / "out"
    (out / "audio").mkdir(parents=True)
    (out / "audio" / "002.wav").write_bytes(b"old")
    entry = {"ordinal": 2, "sha256": "a" * 64, "voice": "Charon",
             "model": "gemini-3.8-flash-tts", "language": "en-GB",
             "instruction": "calm", "alignment": None}
    (out / "synth_record.json").write_text(json.dumps({"scenes": [entry]}))
    code, err = untouched(out, lambda p: synth(capsys, p, *el(FLASH, VOICE, "--scene", "2")))
    assert code == 1
    assert err == DIFF + (
        f'voice recorded "Charon", passed "{VOICE}"; '
        f'model recorded "gemini-3.8-flash-tts", passed "{FLASH}"; '
        'language recorded "en-GB", passed (none); '
        'instruction recorded "calm", passed (none)\n')


def test_empty_alignment_entry_is_malformed(env, capsys):
    out = full_run(env, capsys)
    data = json.loads((out / "synth_record.json").read_text())
    data["scenes"][1]["alignment"]["characters"] = []
    (out / "synth_record.json").write_text(json.dumps(data))
    code, err = untouched(out, lambda p: synth(capsys, p, *el(FLASH, VOICE, "--scene", "2")))
    assert code == 1 and err == MALFORMED + "\n"
