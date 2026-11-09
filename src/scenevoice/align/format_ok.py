from scenevoice.align.record_routing import RecordRouting
from scenevoice.align.scene_timings import SceneTimings


def format_ok(scenes: list[SceneTimings], routing: RecordRouting) -> str:
    """The OK text (no prefix): scene, line and unmatched counts, then the two source counts."""
    lines = [line for scene in scenes for line in scene.lines]
    unmatched = sum(1 for line in lines if line.start_ms is None)
    from_record = sum(1 for route in routing.routes if route is not None)
    return (
        f"OK {len(scenes)} scenes, {len(lines)} lines, {unmatched} unmatched, "
        f"{from_record} from synth record, {len(scenes) - from_record} transcribed"
    )
