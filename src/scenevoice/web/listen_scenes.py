from collections.abc import Mapping

from .planned_scene import PlannedScene
from .record_read import RecordRead


def listen_scenes(scenes: tuple[PlannedScene, ...], record: RecordRead, hashes: Mapping[int, str]) -> int:
    """The estimated number of scenes `align` would send to transcription: a mirror of align check 5a.

    A scene is free only when the record parses, at least one entry for a plan scene has an alignment, and this
    scene's entry has an alignment whose joined characters equal the plan body. Every other scene counts as listened.
    Where the CLI would fail instead (a plan scene with no entry, or an aligned entry whose sha256 differs from its
    WAV's) every scene counts as listened: the documented upper bound, never a refusal.
    """
    total = len(scenes)
    if record.state != "ok":
        return total
    entries = {item.ordinal: item for item in record.items}
    if not any(entries[s.ordinal].characters is not None for s in scenes if s.ordinal in entries):
        return total
    listened = 0
    for scene in scenes:
        entry = entries.get(scene.ordinal)
        if entry is None:
            return total
        if entry.characters is None:
            listened += 1
            continue
        if scene.ordinal in hashes and entry.sha256 != hashes[scene.ordinal]:
            return total
        if entry.characters != scene.body or scene.ordinal not in hashes:
            listened += 1
    return listened
