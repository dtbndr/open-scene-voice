import sys
from dataclasses import replace

import pytest

from scenevoice.web import (
    AudioScan,
    PlannedScene,
    ProjectFacts,
    RecordItem,
    RecordRead,
    TimingsRead,
    can_flags,
    collapse_text,
    job_availability,
    text_witness,
)

SHA, OTHER = "a" * 64, "b" * 64
SCENE = PlannedScene(1, "T", "Hello  there.\r\nNext\xa0line.")


def item(characters):
    return RecordItem(1, SHA, "v", "m", None, None, characters)


def timings(sha=SHA, text="Hello there. Next line."):
    return TimingsRead("ok", {1: (sha, text)})


@pytest.mark.parametrize(
    ("raw", "collapsed"),
    [
        ("a  b", "a b"),
        ("  a\tb\r\n\r\nc  ", "a b c"),
        ("a\xa0b\u2028c\u3000d\u0085e", "a b c d e"),
        ("a\x1cb", "a\x1cb"),
        ("", ""),
        ("one", "one"),
    ],
)
def test_text_is_collapsed_by_unicode_white_space_runs_only(raw, collapsed):
    assert collapse_text(raw) == collapsed


def test_a_record_alignment_is_the_witness_by_exact_joined_characters():
    assert text_witness(SCENE, item(SCENE.body), SHA, TimingsRead("none")) is True
    assert text_witness(SCENE, item(SCENE.body + " "), SHA, TimingsRead("none")) is False
    assert text_witness(SCENE, item("Hello there.\r\nNext\xa0line."), SHA, TimingsRead("none")) is False  # not collapsed


def test_the_alignment_wins_over_a_fresh_line_timings_entry():
    assert text_witness(SCENE, item("other"), SHA, timings()) is False


def test_a_fresh_line_timings_entry_is_the_witness_by_the_collapsed_body_without_an_alignment():
    gemini = item(None)
    assert text_witness(SCENE, gemini, SHA, timings()) is True
    assert text_witness(SCENE, None, SHA, timings()) is True
    assert text_witness(SCENE, gemini, SHA, timings(text="Hello there. Another line.")) is False


@pytest.mark.parametrize(
    ("wav_sha", "table"),
    [
        pytest.param(OTHER, timings(), id="entry-for-other-bytes"),
        pytest.param(None, timings(), id="no-wav-hash"),
        pytest.param(SHA, TimingsRead("none"), id="no-file"),
        pytest.param(SHA, TimingsRead("unreadable"), id="unreadable"),
        pytest.param(SHA, TimingsRead("ok", {2: (SHA, "x")}), id="no-entry-for-the-scene"),
    ],
)
def test_a_gemini_scene_never_aligned_or_with_a_stale_entry_has_no_witness(wav_sha, table):
    assert text_witness(SCENE, item(None), wav_sha, table) is None


SAVE = "Save a script first."
FIX = "Fix the problems in your script first."
STARTED = "Voicing has already started for this project. Choose Voice the rest or Start again."
NOTHING = "Nothing has been voiced yet."
MISMATCH = "What was voiced does not match this script or these settings. Choose Start again."
DIFFER = "One script uses one voice and model. These settings differ from the ones already used."
BEATS_EXIST = "Beats already exist. Choose Redo beats."
NO_BEATS = "There are no beats yet."
VOICE_EVERY = "Voice every scene before this step."
ALL_DONE = "Every scene is already voiced."

SCENES = tuple(PlannedScene(n, f"T{n}", f"Body {n}.") for n in (1, 2, 3))
H = {n: chr(96 + n) * 64 for n in range(1, 10)}
SETTINGS = {"voice": "Leda", "model": "gemini-3.8-flash-tts", "language": "en-GB", "instruction": None}


def entry(n, **changes):
    return replace(RecordItem(n, H[n], "Leda", "gemini-3.8-flash-tts", "en-GB", None, None), **changes)


def facts(voiced=(), named=None, items=None, record="ok", beats="none", script="ok", scenes=SCENES, timings=None):
    named = tuple(voiced) if named is None else named
    items = tuple(entry(n) for n in voiced) if items is None else items
    return ProjectFacts(
        script, scenes if script == "ok" else (), AudioScan(tuple(named), {n: H[n] for n in voiced}),
        RecordRead(record, items if record == "ok" else ()), timings or TimingsRead("none"), beats,
    )


def flags(all=False, rest=False, restart=False, scene=False, align=False, beats=False, redo=False, pack=False):
    return {"synth": {"all": all, "rest": rest, "restart": restart}, "synth_scene": scene, "align": align, "beats": beats, "beats_redo": redo, "pack": pack}


ALL_VOICED = (1, 2, 3)
ROWS = [
    pytest.param(facts(script="none"), flags(), id="no-script"),
    pytest.param(facts(script="problem"), flags(), id="script-problem"),
    pytest.param(facts(), flags(all=True, restart=True, beats=True), id="script-ok-nothing-voiced"),
    pytest.param(facts((1, 2)), flags(rest=True, restart=True, scene=True, beats=True), id="some-voiced-consistent"),
    pytest.param(facts(ALL_VOICED), flags(restart=True, scene=True, align=True, beats=True, pack=True), id="all-voiced"),
    pytest.param(facts((1, 2), record="none"), flags(restart=True, beats=True), id="voiced-no-record"),
    pytest.param(facts((1, 2), items=(entry(1), entry(2, voice="Zephyr"))), flags(restart=True, beats=True), id="voiced-inconsistent-settings"),
    pytest.param(facts((1, 2), items=(entry(1), entry(2, characters="Edited text."))), flags(restart=True, scene=True, beats=True), id="false-witness-blocks-rest-not-a-single-scene"),
    pytest.param(facts(ALL_VOICED, beats="fresh"), flags(restart=True, scene=True, align=True, redo=True, pack=True), id="all-voiced-beats-fresh"),
    pytest.param(facts((1,), beats="stale"), flags(rest=True, restart=True, scene=True, redo=True), id="beats-stale"),
]


@pytest.mark.parametrize(("project", "expected"), ROWS)
def test_the_can_flags_follow_the_facts(project, expected):
    assert can_flags(project) == expected


@pytest.mark.parametrize(
    ("project", "kind", "mode", "message"),
    [
        pytest.param(facts(script="none"), "synth", "all", SAVE, id="save-first"),
        pytest.param(facts(script="problem"), "synth", "restart", FIX, id="fix-first"),
        pytest.param(facts((1,)), "synth", "all", STARTED, id="all-after-voicing-started"),
        pytest.param(facts(), "synth", "rest", NOTHING, id="rest-nothing-voiced"),
        pytest.param(facts((1,), record="none"), "synth", "rest", MISMATCH, id="rest-no-record"),
        pytest.param(facts((1, 2), items=(entry(1), entry(2, model="x"))), "synth-scene", None, MISMATCH, id="scene-inconsistent"),
        pytest.param(facts(ALL_VOICED), "synth", "rest", ALL_DONE, id="rest-all-voiced"),
        pytest.param(facts((1,)), "align", None, VOICE_EVERY, id="align-partial"),
        pytest.param(facts(beats="stale"), "beats", None, BEATS_EXIST, id="beats-exist-stale"),
        pytest.param(facts(), "beats-redo", None, NO_BEATS, id="redo-without-beats"),
    ],
)
def test_each_refusal_is_its_j12_message(project, kind, mode, message):
    assert job_availability(project, kind, mode) == message


def test_allowed_requests_answer_none_and_restart_needs_only_a_script():
    assert job_availability(facts(), "synth", "restart") is None
    assert job_availability(facts((1, 2), record="none"), "synth", "restart") is None
    assert job_availability(facts(ALL_VOICED, beats="fresh"), "beats-redo") is None


@pytest.mark.parametrize(
    ("requested", "message"),
    [
        pytest.param(dict(SETTINGS), None, id="same-settings"),
        pytest.param({"voice": "Zephyr"}, DIFFER, id="other-voice"),
        pytest.param({"model": "eleven_flash_v2_5"}, DIFFER, id="other-model"),
        pytest.param({"language": None}, DIFFER, id="other-language"),
    ],
)
@pytest.mark.parametrize(("kind", "mode"), [("synth", "rest"), ("synth-scene", None)])
def test_settings_that_differ_from_the_recorded_ones_are_refused_for_rest_and_scene(kind, mode, requested, message):
    assert job_availability(facts((1, 2)), kind, mode, requested) == message


def test_a_refusal_of_the_rest_check_wins_over_a_settings_comparison():
    assert job_availability(facts((1,), record="none"), "synth", "rest", {"voice": "Zephyr"}) == MISMATCH


def test_the_flags_call_the_one_availability_function_for_every_kind_and_mode(monkeypatch):
    asked = []
    module = sys.modules["scenevoice.web.can_flags"]
    monkeypatch.setattr(module, "job_availability", lambda *args: asked.append(args[1:]))
    assert can_flags(facts())["pack"] is True  # positive control: the patched function answered None for all
    assert asked == [
        ("synth", "all"), ("synth", "rest"), ("synth", "restart"), ("synth-scene", None), ("align", None),
        ("beats", None), ("beats-redo", None), ("pack", None),
    ]


def test_a_single_scene_needs_the_audio_folder_even_with_a_record():
    voiced = facts((1, 2))
    gone = replace(voiced, audio=AudioScan(voiced.audio.named, voiced.audio.hashes, folder=False))
    assert job_availability(voiced, "synth-scene", None, {}) is None
    assert job_availability(gone, "synth-scene", None, {}) == NOTHING
    assert can_flags(gone)["synth_scene"] is False
