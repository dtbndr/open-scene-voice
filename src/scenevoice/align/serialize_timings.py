import json

from scenevoice.align.scene_timings import SceneTimings


def serialize_timings(scenes: list[SceneTimings]) -> bytes:
    """Return the exact bytes of line_timings.json: indent 2, raw non-ASCII, one LF."""
    document = {
        "scenes": [
            {
                "ordinal": scene.ordinal,
                "sha256": scene.sha256,
                "lines": [
                    {"text": line.text, "start_ms": line.start_ms}
                    for line in scene.lines
                ],
            }
            for scene in scenes
        ]
    }
    text = json.dumps(document, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")
