"""Editor runs (--editor resolve) against plain runs: what is written, and the zero-frame rule.
"""

import os

import pytest
from pack_run_helper import MISSING_NOTE, make_out, ok_line, run, run_text, write_plan

from scenevoice.pack import build_manifest, build_timeline, format_duration
from scenevoice.synth import PlanScene

HEADER = b"scene,label,file,duration_s\n"


def scene(ordinal, title):
    return PlanScene(ordinal=ordinal, title=title, body="x")


def test_contract_two_row_example():
    scenes = [scene(1, "Café, au lait"), scene(2, 'The "big" day')]
    expected = (
        b"scene,label,file,duration_s\n"
        b'1,"Caf\xc3\xa9, au lait",audio/001.wav,2.100\n'
        b'2,"The ""big"" day",audio/002.wav,5.144\n'
    )
    assert build_manifest(scenes, [50400, 123456]) == expected


def test_cr_title_row_matches_contract_hex():
    row = bytes.fromhex("312c22610d62222c617564696f2f3030312e7761762c312e3530300a")
    assert build_manifest([scene(1, "a\rb")], [36000]) == HEADER + row


def test_lf_title_is_quoted_with_lf_kept():
    assert build_manifest([scene(1, "a\nb")], [36000]) == HEADER + b'1,"a\nb",audio/001.wav,1.500\n'


def test_crlf_title_keeps_cr_lf_inside_quotes_only():
    out = build_manifest([scene(1, "a\r\nb")], [36000])
    assert out == HEADER + b'1,"a\r\nb",audio/001.wav,1.500\n'


def test_empty_title_is_bare():
    assert build_manifest([scene(1, "")], [50400]) == HEADER + b"1,,audio/001.wav,2.100\n"


def test_title_of_only_a_double_quote():
    assert build_manifest([scene(1, '"')], [50400]) == HEADER + b'1,"""",audio/001.wav,2.100\n'


def test_scene_prefix_kept_verbatim():
    out = build_manifest([scene(3, "Scene 3: Intro")], [24000])
    assert out == HEADER + b"3,Scene 3: Intro,audio/003.wav,1.000\n"


def test_leading_and_trailing_spaces_kept():
    out = build_manifest([scene(1, "  pad  ")], [24000])
    assert out == HEADER + b"1,  pad  ,audio/001.wav,1.000\n"


@pytest.mark.parametrize(
    ("frames", "expected"),
    [
        (1, "0.000"),
        (11, "0.000"),
        (12, "0.001"),
        (36, "0.002"),
        (24000, "1.000"),
        (123456, "5.144"),
        (10_000_020, "416.668"),
    ],
)
def test_format_duration_table(frames, expected):
    result = format_duration(frames)
    assert result == expected
    assert isinstance(result, str)
    assert result.split(".")[1].__len__() == 3


MANIFEST = "scene_manifest.csv"


TIMELINE = "resolve_timeline.otio"


def test_editor_run_writes_both_files_with_one_note_and_one_ok_line(tmp_path, capsys):
    out = make_out(tmp_path)
    code, text = run(tmp_path, out)
    assert code == 0
    assert text == MISSING_NOTE + ok_line(out)
    assert sorted(os.listdir(out)) == ["audio", TIMELINE, MANIFEST]
    assert capsys.readouterr().out == ""


def test_manifest_bytes_equal_the_plain_run(tmp_path):
    plan = write_plan(tmp_path)
    a, b = make_out(tmp_path, "a"), make_out(tmp_path, "b")
    assert run_text(plan, a, "resolve")[0] == 0
    assert run_text(plan, b)[0] == 0
    assert (a / MANIFEST).read_bytes() == (b / MANIFEST).read_bytes()


def test_timeline_is_build_timeline_of_the_plan_and_frames(tmp_path):
    out = make_out(tmp_path)
    run(tmp_path, out)
    scenes = [PlanScene(1, "One", "Hello."), PlanScene(2, "Two", "Hello.")]
    assert (out / TIMELINE).read_bytes() == build_timeline(scenes, [24000, 12000])[0]


def test_plain_run_never_touches_a_timeline_and_says_no_note(tmp_path):
    out = make_out(tmp_path)
    (out / TIMELINE).write_bytes(b"old")
    code, text = run_text(write_plan(tmp_path), out)
    assert code == 0
    assert text == f"scenevoice pack: OK 2 scenes written to {out}/{MANIFEST}\n"
    assert (out / TIMELINE).read_bytes() == b"old"


def test_999_frame_wav_passes_plain_and_fails_an_editor_run_writing_nothing(tmp_path):
    plain = make_out(tmp_path, "plain", frames=(999, 12000))
    code, _ = run_text(write_plan(tmp_path), plain)
    assert code == 0
    assert "0.042" in (plain / MANIFEST).read_text()
    editor = make_out(tmp_path, "editor", frames=(999, 12000))
    before = sorted(os.listdir(editor))
    code, text = run(tmp_path, editor)
    assert code == 1
    assert text.startswith("scenevoice pack: FAIL scene 1: audio/001.wav: ")
    assert sorted(os.listdir(editor)) == before
