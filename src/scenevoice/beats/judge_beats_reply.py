from scenevoice.beats.build_sidecar import build_sidecar
from scenevoice.beats.check_beats_coverage import check_beats_coverage
from scenevoice.beats.parse_beats_reply import parse_beats_reply
from scenevoice.beats.serialise_sidecar import serialise_sidecar
from scenevoice.validation.scene import Scene


def judge_beats_reply(
    cleaned: str,
    truncated: bool,
    script_bytes: bytes,
    scenes: list[Scene],
    segments: list[list[str]],
) -> tuple[str, list[str], int]:
    """Return (text to write, problems, beat count).

    Only a complete, valid reply becomes the canonical sidecar; anything else is
    written as the cleaned raw reply so it fails the sidecar shape check.
    """
    parsed, problem = parse_beats_reply(cleaned)
    if parsed is None:
        return cleaned, [problem or "the reply is not valid beats JSON"], 0
    counts = [len(scene_segments) for scene_segments in segments]
    problems = check_beats_coverage(counts, parsed)
    if problems or truncated:
        return cleaned, problems, 0
    sidecar = build_sidecar(script_bytes, scenes, counts, parsed)
    beat_count = sum(len(scene["beats"]) for scene in sidecar["scenes"])
    return serialise_sidecar(sidecar), [], beat_count
