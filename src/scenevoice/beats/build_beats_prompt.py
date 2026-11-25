from scenevoice.beats.beats_constants import MAX_NOTE_CHARS
from scenevoice.validation.scene import Scene

SYSTEM_PROMPT = f"""You split a narrated video script into visual beats for a video editor.
The script is given as scenes ("Scene N: title"). Each scene is a numbered list of segments (sentences).
Group the segments of each scene into beats: a beat is one visual idea the editor would cover with one shot or B-roll clip.
Beats are contiguous and in order, and together they cover every numbered segment of the scene exactly once, with no gaps and no overlaps.
For each beat give the first and last segment number it covers (inclusive) and a note: a short single-line description of the picture to show (not blank, at most {MAX_NOTE_CHARS} characters).
Rules: describe only: no timing, no cues, no rewriting.
A scene listed with no segments gets an empty beats list.
Reply with a single JSON object and nothing else, in this shape:
{{"scenes": [{{"scene": 1, "beats": [{{"first": 1, "last": 2, "note": "..."}}]}}]}}
Use the scene numbers from the "Scene N:" lines and the segment numbers exactly as given."""


def build_beats_prompt(
    scenes: list[Scene], segments: list[list[str]]
) -> list[dict[str, str]]:
    """Return the chat messages; segment numbers are per scene and 1-based."""
    lines: list[str] = []
    for scene, scene_segments in zip(scenes, segments, strict=True):
        lines.append(f"Scene {scene.ordinal}: {scene.title}")
        if not scene_segments:
            lines.append("(no segments)")
        for number, text in enumerate(scene_segments, start=1):
            lines.append(f"{number}. {text}")
        lines.append("")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(lines).rstrip() + "\n"},
    ]
