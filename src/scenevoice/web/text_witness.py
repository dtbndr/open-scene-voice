from .collapse_text import collapse_text
from .planned_scene import PlannedScene
from .record_item import RecordItem
from .timings_read import TimingsRead


def text_witness(scene: PlannedScene, item: RecordItem | None, wav_sha256: str | None, timings: TimingsRead) -> bool | None:
    """Whether the stored text of a voiced scene still equals the plan body: True, False, or None with no witness.

    The witness is the record entry's alignment (its joined characters, exactly the body) and otherwise a FRESH
    `line_timings.json` entry (its sha256 equals the WAV's) whose line texts, joined by a space, equal the body with
    whitespace collapsed. A Gemini scene never aligned has no witness.
    """
    if item is not None and item.characters is not None:
        return item.characters == scene.body
    entry = timings.entries.get(scene.ordinal) if timings.state == "ok" else None
    if entry is not None and wav_sha256 is not None and entry[0] == wav_sha256:
        return entry[1] == collapse_text(scene.body)
    return None
