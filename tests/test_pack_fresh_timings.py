import hashlib

from scenevoice.pack import (
    MISSING_FILE_NOTE,
    LineTiming,
    fresh_timings,
    skipped_marker_note,
    timings_notes,
)

WAV1 = b"wav-one"
WAV2 = b"wav-two"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def line(text="x", start=0):
    return LineTiming(text, start)


def test_equal_hash_is_fresh():
    table = {1: (sha(WAV1), [line()])}
    result = fresh_timings(table, [(1, WAV1)])
    assert result.fresh == {1: [line()]}
    assert result.unusable == []
    assert timings_notes(result) == []


def test_different_hash_is_stale_and_absent_from_fresh():
    table = {1: (sha(b"other"), [line()])}
    result = fresh_timings(table, [(1, WAV1)])
    assert result.fresh == {}
    assert result.unusable == [(1, "stale")]
    notes = timings_notes(result)
    assert len(notes) == 1
    assert notes[0].startswith("scenevoice pack: NOTE scene 1: ")
    assert "stale" in notes[0]


def test_no_entry_is_missing():
    result = fresh_timings({}, [(2, WAV1)])
    assert result.fresh == {}
    assert result.unusable == [(2, "missing")]
    (note,) = timings_notes(result)
    assert note.startswith("scenevoice pack: NOTE scene 2: ")
    assert "no line timings entry" in note


def test_fresh_entry_with_empty_lines_is_fresh_and_has_no_note():
    result = fresh_timings({1: (sha(WAV1), [])}, [(1, WAV1)])
    assert result.fresh == {1: []}
    assert timings_notes(result) == []


def test_stale_entry_with_empty_lines_still_notes():
    result = fresh_timings({1: (sha(b"other"), [])}, [(1, WAV1)])
    assert result.unusable == [(1, "stale")]
    assert len(timings_notes(result)) == 1


def test_entry_for_scene_not_in_plan_is_ignored():
    table = {9: (sha(WAV1), [line()])}
    result = fresh_timings(table, [(1, WAV1)])
    assert 9 not in result.fresh
    assert result.unusable == [(1, "missing")]


def test_mixed_scenes_notes_follow_plan_order():
    table = {2: (sha(b"old"), [line()]), 3: (sha(WAV2), [line("y", 5)])}
    result = fresh_timings(table, [(1, WAV1), (2, WAV1), (3, WAV2)])
    assert result.fresh == {3: [line("y", 5)]}
    assert result.unusable == [(1, "missing"), (2, "stale")]
    notes = timings_notes(result)
    assert "scene 1" in notes[0] and "scene 2" in notes[1]


def test_hash_is_of_the_held_bytes_not_of_a_name():
    table = {1: (sha(WAV1), [line()])}
    assert fresh_timings(table, [(1, WAV2)]).unusable == [(1, "stale")]


def test_pinned_note_wording():
    assert MISSING_FILE_NOTE == (
        "scenevoice pack: NOTE no line_timings.json, scene markers only"
    )
    (missing,) = timings_notes(fresh_timings({}, [(4, WAV1)]))
    assert missing == "scenevoice pack: NOTE scene 4: no line timings entry, scene marker only"
    (stale_note,) = timings_notes(fresh_timings({4: (sha(b"o"), [])}, [(4, WAV1)]))
    assert stale_note == "scenevoice pack: NOTE scene 4: line timings stale, scene marker only"
    assert skipped_marker_note(3, 2) == (
        "scenevoice pack: NOTE scene 3 line 2: marker skipped, no free frame"
    )
