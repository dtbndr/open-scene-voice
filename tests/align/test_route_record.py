from pathlib import Path

import pytest
from record_helper import (
    RECORD_FILE,
    eleven_entry,
    gemini_entry,
    per_char_alignment,
    sha_of,
    write_record,
)
from wav_helper import make_wav

from scenevoice.align import RecordRouting, SceneTimings, route_record
from scenevoice.synth import PlanScene, SceneWav

BODIES = {1: "Hello there.", 2: "Second one.", 3: "Third one."}


def _scenes(count: int = 3) -> list[PlanScene]:
    return [PlanScene(n, f"T{n}", BODIES[n]) for n in range(1, count + 1)]


def _wavs(count: int = 3) -> list[SceneWav]:
    return [SceneWav(make_wav(frames=10 + n), 10 + n) for n in range(1, count + 1)]


def _eleven(wavs: list[SceneWav], n: int, **kw) -> dict:
    return eleven_entry(n, wavs[n - 1].data, BODIES[n], **kw)


def _route(tmp_path: Path, count: int = 3):
    return route_record(_scenes(count), _wavs(count), tmp_path)


def _routing(result: RecordRouting | str) -> RecordRouting:
    assert isinstance(result, RecordRouting)
    return result


def _fail(result: RecordRouting | str) -> str:
    assert isinstance(result, str)
    return result


def _all_transcribe(routing: RecordRouting, count: int = 3) -> None:
    assert routing.routes == (None,) * count


def test_directory_at_record_name_fails(tmp_path: Path) -> None:
    (tmp_path / RECORD_FILE).mkdir()
    assert RECORD_FILE in _fail(_route(tmp_path))


def test_symlink_to_regular_file_fails(tmp_path: Path) -> None:
    target = tmp_path / "real.json"
    target.write_text('{"scenes": []}')
    (tmp_path / RECORD_FILE).symlink_to(target)
    assert RECORD_FILE in _fail(_route(tmp_path))


def test_dangling_symlink_fails(tmp_path: Path) -> None:
    (tmp_path / RECORD_FILE).symlink_to(tmp_path / "nowhere.json")
    assert RECORD_FILE in _fail(_route(tmp_path))


def test_absent_file_transcribes_all_with_no_file_flag(tmp_path: Path) -> None:
    routing = _routing(_route(tmp_path))
    _all_transcribe(routing)
    assert routing.no_file is True
    assert routing.mismatched == ()


@pytest.mark.parametrize(
    "text",
    ["not json", '{"scenes": [{"ordinal": 1}]}', '{"other": []}'],
)
def test_malformed_record_fails_without_synth_hint(tmp_path: Path, text: str) -> None:
    (tmp_path / RECORD_FILE).write_text(text)
    message = _fail(_route(tmp_path))
    assert RECORD_FILE in message
    assert "delete" not in message
    assert "--scene" not in message


def test_unknown_model_is_malformed(tmp_path: Path) -> None:
    wavs = _wavs()
    entry = gemini_entry(1, wavs[0].data)
    entry["model"] = "no-such-model"
    write_record(tmp_path, entry)
    message = _fail(_route(tmp_path))
    assert RECORD_FILE in message
    assert "--scene" not in message


def test_gemini_pack_transcribes_all_without_notes(tmp_path: Path) -> None:
    wavs = _wavs()
    # a wrong sha256 and a missing entry (scene 3) are irrelevant in a Gemini pack
    write_record(
        tmp_path,
        gemini_entry(1, wavs[0].data),
        gemini_entry(2, wavs[1].data, sha256="0" * 64),
    )
    routing = _routing(_route(tmp_path))
    _all_transcribe(routing)
    assert routing.no_file is False
    assert routing.mismatched == ()


def test_empty_record_is_a_gemini_pack(tmp_path: Path) -> None:
    write_record(tmp_path)
    routing = _routing(_route(tmp_path))
    _all_transcribe(routing)
    assert routing.no_file is False


def test_out_of_plan_eleven_entry_with_gemini_in_plan_is_gemini_pack(
    tmp_path: Path,
) -> None:
    wavs = _wavs(2)
    write_record(
        tmp_path,
        gemini_entry(1, wavs[0].data),
        eleven_entry(9, b"x", "Nine."),
    )
    routing = _routing(_route(tmp_path, 2))
    _all_transcribe(routing, 2)
    assert routing.no_file is False


def test_out_of_plan_entry_with_bad_sha_is_ignored_in_eleven_pack(
    tmp_path: Path,
) -> None:
    wavs = _wavs(2)
    write_record(
        tmp_path,
        _eleven(wavs, 1),
        _eleven(wavs, 2),
        eleven_entry(9, b"x", "Nine.", sha256="f" * 64),
    )
    routing = _routing(_route(tmp_path, 2))
    assert all(isinstance(r, SceneTimings) for r in routing.routes)


def test_missing_entry_in_eleven_pack_fails_naming_scene(tmp_path: Path) -> None:
    wavs = _wavs()
    write_record(tmp_path, _eleven(wavs, 1), _eleven(wavs, 3))
    message = _fail(_route(tmp_path))
    assert RECORD_FILE in message
    assert "scene 2" in message
    assert "synth --scene 2" in message


def test_sha_mismatch_fails_naming_scene(tmp_path: Path) -> None:
    wavs = _wavs()
    write_record(
        tmp_path, _eleven(wavs, 1), _eleven(wavs, 2, sha256="0" * 64), _eleven(wavs, 3)
    )
    message = _fail(_route(tmp_path))
    assert RECORD_FILE in message
    assert "scene 2" in message
    assert "synth --scene 2" in message


def test_characters_differing_by_one_extra_char_transcribe_with_note(
    tmp_path: Path,
) -> None:
    wavs = _wavs()
    write_record(
        tmp_path,
        _eleven(wavs, 1),
        eleven_entry(2, wavs[1].data, BODIES[2] + "!"),
        _eleven(wavs, 3),
    )
    routing = _routing(_route(tmp_path))
    assert routing.mismatched == (2,)
    assert routing.routes[1] is None
    # scenes 1 and 3 are unaffected: positive control that the record was accepted
    assert isinstance(routing.routes[0], SceneTimings)
    assert isinstance(routing.routes[2], SceneTimings)
    assert routing.no_file is False


def test_crlf_body_against_lf_record_transcribes_with_note(tmp_path: Path) -> None:
    wavs = _wavs(1)
    scenes = [PlanScene(1, "T", "One.\r\nTwo.")]
    write_record(tmp_path, eleven_entry(1, wavs[0].data, "One.\nTwo."))
    routing = _routing(route_record(scenes, wavs, tmp_path))
    assert routing.routes == (None,)
    assert routing.mismatched == (1,)


def test_matching_entry_takes_record_timings(tmp_path: Path) -> None:
    wavs = _wavs()
    write_record(tmp_path, _eleven(wavs, 1), _eleven(wavs, 2), _eleven(wavs, 3))
    routing = _routing(_route(tmp_path))
    assert routing.mismatched == ()
    assert routing.no_file is False
    for n, timings in enumerate(routing.routes, start=1):
        assert isinstance(timings, SceneTimings)
        assert timings.ordinal == n
        assert timings.sha256 == sha_of(wavs[n - 1].data)
        assert [line.start_ms for line in timings.lines] == [0]


def test_overflow_on_record_scene_fails_naming_scene(tmp_path: Path) -> None:
    wavs = _wavs(2)
    big = per_char_alignment(BODIES[2])
    big["character_start_times_seconds"][0] = 1e306
    write_record(tmp_path, _eleven(wavs, 1), _eleven(wavs, 2, alignment=big))
    message = _fail(_route(tmp_path, 2))
    assert RECORD_FILE in message
    assert "scene 2" in message


def test_overflow_value_on_mismatched_scene_does_not_fail(tmp_path: Path) -> None:
    wavs = _wavs(2)
    big = per_char_alignment(BODIES[2] + "!")
    big["character_start_times_seconds"][0] = 1e306
    write_record(
        tmp_path, _eleven(wavs, 1), eleven_entry(2, wavs[1].data, "", alignment=big)
    )
    routing = _routing(_route(tmp_path, 2))
    assert routing.mismatched == (2,)
    assert routing.routes[1] is None
    assert isinstance(routing.routes[0], SceneTimings)


def test_first_failing_scene_missing_before_later_mismatch(tmp_path: Path) -> None:
    wavs = _wavs()
    write_record(tmp_path, _eleven(wavs, 1), _eleven(wavs, 3, sha256="0" * 64))
    assert "scene 2" in _fail(_route(tmp_path))


def test_first_failing_scene_overflow_before_later_missing(tmp_path: Path) -> None:
    """Mutation: computing overflow in a second pass after routing all scenes reports scene 2."""
    wavs = _wavs(2)
    big = per_char_alignment(BODIES[1])
    big["character_start_times_seconds"][0] = 1e306
    write_record(
        tmp_path, _eleven(wavs, 1, alignment=big), eleven_entry(3, b"x", "Third one.")
    )
    message = _fail(_route(tmp_path, 2))
    assert "scene 1" in message
    assert "scene 2" not in message


def test_sha_mismatch_wins_over_character_mismatch(tmp_path: Path) -> None:
    """Order (e) before (f). Mutation: checking characters before sha makes this scene transcribe."""
    wavs = _wavs(1)
    write_record(
        tmp_path, eleven_entry(1, wavs[0].data, BODIES[1] + "!", sha256="0" * 64)
    )
    message = _fail(route_record(_scenes(1), wavs, tmp_path))
    assert "scene 1" in message
    assert "synth --scene 1" in message


def test_character_mismatch_is_transcribed_not_taken_from_record(
    tmp_path: Path,
) -> None:
    """Order (f) before (g). Mutation: skipping (f) calls record_scene, which raises IndexError."""
    wavs = _wavs(1)
    write_record(tmp_path, eleven_entry(1, wavs[0].data, "Hello"))
    routing = _routing(route_record(_scenes(1), wavs, tmp_path))
    assert routing.routes == (None,)
    assert routing.mismatched == (1,)


def test_missing_entry_never_reaches_hash_comparison(tmp_path: Path) -> None:
    """Order (c) first. Mutation: reading entry.sha256 before the missing check raises
    AttributeError/KeyError (a test error, not a FAIL line); the assertion fails either way."""
    wavs = _wavs()
    write_record(tmp_path, _eleven(wavs, 1), _eleven(wavs, 3))
    assert "scene 2" in _fail(_route(tmp_path))
