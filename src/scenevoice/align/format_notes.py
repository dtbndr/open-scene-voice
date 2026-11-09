from scenevoice.align.record_routing import RecordRouting
from scenevoice.align.scene_timings import SceneTimings


def format_notes(scenes: list[SceneTimings], routing: RecordRouting) -> list[str]:
    """NOTE texts (no prefix) in contract order.

    The no-file NOTE first, then per scene in plan order its character-mismatch NOTE before its
    line NOTEs (one per null start_ms).
    """
    notes = ["NOTE no synth_record.json, all scenes transcribed"] if routing.no_file else []
    for scene in scenes:
        if scene.ordinal in routing.mismatched:
            notes.append(f"NOTE scene {scene.ordinal}: alignment text differs from plan body, transcribed")
        notes.extend(
            f"NOTE scene {scene.ordinal} line {number}: no match, start_ms null"
            for number, line in enumerate(scene.lines, start=1)
            if line.start_ms is None
        )
    return notes
