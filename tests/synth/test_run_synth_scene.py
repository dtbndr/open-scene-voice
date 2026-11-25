"""synth --scene N refusals on an ElevenLabs directory (D14, D21): offline, injected post, no network."""

import json
import sys

import pytest
from elevenlabs_scene_helper import (
    DIFF,
    FLASH,
    PREFIX,
    V4,
    VOICE,
    el,
    full_run,
    setup_env,
    synth,
    untouched,
)
from synth_scene_helper import (
    NEW_AUDIO,
    Call,
    Rec,
    make_out,
    make_plan,
    no_temp,
    run,
    snapshot,
)
from wav_helper import make_wav

from scenevoice.synth import ENV_NAMES, ProviderAudio, ProviderError
from scenevoice.synth.regen_notes import missing_record_note

WRITE_MODULE = "scenevoice.synth.write_wav"


def test_replaces_only_selected_scene_with_one_call(tmp_path, capsys):
    out = make_out(tmp_path)
    before = snapshot(out)
    rec = Rec()
    code, err = run(tmp_path, rec, scene=2)
    assert code == 0
    assert rec.calls == [Call("body 2", "Callirrhoe", "en-GB", "calm")]
    after = snapshot(out)
    assert after["002.wav"] == NEW_AUDIO.wav != before["002.wav"]
    assert after["001.wav"] == before["001.wav"]
    assert after["003.wav"] == before["003.wav"]
    assert no_temp(out)
    assert capsys.readouterr().out == ""
    assert err.splitlines() == [
        PREFIX + "NOTE " + missing_record_note(2),
        PREFIX + "scene 2/3 written to audio/002.wav",
        PREFIX + f"OK scene 2 written to {out / 'audio' / '002.wav'}",
    ]
    assert rec.factory_calls == 1


def test_absent_target_is_created(tmp_path):
    out = make_out(tmp_path, names=("001.wav",))
    code, err = run(tmp_path, Rec(), scene=3)
    assert code == 0
    assert (out / "audio" / "003.wav").read_bytes() == NEW_AUDIO.wav
    assert err.splitlines()[0] == PREFIX + "NOTE " + missing_record_note(3)
    assert err.splitlines()[1] == PREFIX + "scene 3/3 written to audio/003.wav"


def _bad(audio):
    return lambda: audio


@pytest.mark.parametrize(
    "impl",
    [
        lambda: (_ for _ in ()).throw(ProviderError("boom")),
        _bad(ProviderAudio("audio/mpeg", make_wav())),
    ],
    ids=["provider-error", "invalid-audio"],
)
def test_failures_keep_old_file(tmp_path, impl):
    out = make_out(tmp_path)
    before = snapshot(out)
    rec = Rec(impl)
    code, err = run(tmp_path, rec, scene=2)
    assert code == 1
    assert err.splitlines()[-1].startswith(PREFIX + "FAIL ")
    assert len(rec.calls) == 1
    assert snapshot(out) == before
    assert no_temp(out)


def test_write_failure_keeps_old_file(tmp_path, monkeypatch):
    out = make_out(tmp_path)
    before = snapshot(out)
    reached = []
    mod = sys.modules[WRITE_MODULE]

    def boom(src, dst):
        reached.append(dst)
        raise OSError("rename failed")

    monkeypatch.setattr(mod.os, "replace", boom)
    code, err = run(tmp_path, Rec(), scene=2)
    assert reached, "positive control: the patched os.replace was reached"
    assert code == 1
    assert err.splitlines()[-1].startswith(PREFIX + "FAIL ")
    assert snapshot(out) == before
    assert no_temp(out)


def test_full_run_unchanged_without_scene(tmp_path):
    plan = make_plan(tmp_path)
    rec = Rec()
    code, err = run(tmp_path, rec, scene=None, plan=plan)
    out = tmp_path / "out"
    assert code == 0 and len(rec.calls) == 3
    assert err.splitlines()[-1] == PREFIX + f"OK 3 scenes written to {out}"
    assert err.splitlines()[0] == PREFIX + "scene 1/3 written to audio/001.wav"
    rec2 = Rec()
    code, err = run(tmp_path, rec2, scene=None, plan=plan)
    assert code == 1 and "001.wav" in err and rec2.factory_calls == 0


def tree(out):
    return {p.name: p.read_bytes() if p.is_file() else None for p in (out / "audio").iterdir()}


def ready(tmp_path, **kw):
    make_out(tmp_path)
    return kw


def missing_out(tmp_path):
    return {}


def non_regular_target(tmp_path):
    (make_out(tmp_path, names=("001.wav",)) / "audio" / "002.wav").mkdir()
    return {}


def missing_audio_dir(tmp_path):
    (tmp_path / "out").mkdir()
    return {}


def invalid_plan(tmp_path):
    make_out(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    return {"plan": bad}


def over_limit_other_scene(tmp_path):
    make_out(tmp_path)
    return {"scene": 1, "plan": make_plan(tmp_path, bodies={3: "x" * 100000})}


CASES = {
    "bad-scene": lambda t: ready(t, scene=4),
    "missing-keys": lambda t: ready(t, env={}),
    "missing-out": missing_out,
    "missing-audio-dir": missing_audio_dir,
    "non-regular-target": non_regular_target,
    "invalid-plan": invalid_plan,
    "over-limit-other-scene": over_limit_other_scene,
}


@pytest.mark.parametrize("case", CASES)
def test_preflight_failure_makes_no_provider_calls_and_changes_nothing(tmp_path, case):
    kw = CASES[case](tmp_path)
    audio = tmp_path / "out" / "audio"
    before = tree(tmp_path / "out") if audio.is_dir() else None
    rec = Rec()
    code, err = run(tmp_path, rec, **kw)
    assert code == 1 and err.startswith(PREFIX + "FAIL ")
    assert rec.factory_calls == 0 and rec.calls == []
    if before is not None:
        assert tree(tmp_path / "out") == before
    elif case == "missing-out":
        assert not (tmp_path / "out").exists()


@pytest.fixture
def env(tmp_path, monkeypatch):
    return setup_env(tmp_path, monkeypatch)


@pytest.mark.parametrize(
    "args, recorded",
    [
        (el(FLASH, "other", "--scene", "2"), f'voice recorded "{VOICE}", passed "other"'),
        (el(V4, VOICE, "--scene", "2"), f'model recorded "{FLASH}", passed "{V4}"'),
        (
            ("--voice", "Charon", "--model", "gemini-3.8-flash-tts", "--scene", "2"),
            f'model recorded "{FLASH}", passed "gemini-3.8-flash-tts"',
        ),
    ],
    ids=["voice", "model", "gemini-run-on-elevenlabs-entry"],
)
def test_settings_that_differ_from_the_record_are_refused_untouched(env, capsys, monkeypatch, args, recorded):
    out = full_run(env, capsys)
    for name in ENV_NAMES:
        monkeypatch.setenv(name, "vertex-dummy-value")
    code, err = untouched(out, lambda p: synth(capsys, p, *args))
    assert code == 1
    assert err.startswith(DIFF) and recorded in err


def test_elevenlabs_run_on_a_gemini_entry_is_refused_untouched(env, capsys):
    out = env / "out"
    (out / "audio").mkdir(parents=True)
    (out / "audio" / "002.wav").write_bytes(b"old")
    entry = {"ordinal": 2, "sha256": "a" * 64, "voice": "Charon", "model": "gemini-3.8-flash-tts",
             "language": "en-GB", "instruction": "calm", "alignment": None}  # fmt: skip
    (out / "synth_record.json").write_text(json.dumps({"scenes": [entry]}))
    code, err = untouched(out, lambda p: synth(capsys, p, *el(FLASH, VOICE, "--scene", "2")))
    assert code == 1
    assert err.startswith(DIFF) and 'language recorded "en-GB", passed (none)' in err


def test_empty_alignment_entry_is_a_malformed_record(env, capsys):
    out = full_run(env, capsys)
    data = json.loads((out / "synth_record.json").read_text())
    data["scenes"][1]["alignment"]["characters"] = []
    (out / "synth_record.json").write_text(json.dumps(data))
    code, err = untouched(out, lambda p: synth(capsys, p, *el(FLASH, VOICE, "--scene", "2")))
    assert code == 1 and err.startswith(PREFIX + "FAIL synth_record.json")
