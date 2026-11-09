from dataclasses import dataclass

from scenevoice.align.scene_timings import SceneTimings


@dataclass(frozen=True)
class RecordRouting:
    """Check 5a result: per-scene routing in plan order and the routing NOTE inputs.

    routes holds a scene's record-path timings, or None when the scene is transcribed.
    mismatched lists the ordinals that get the character-mismatch NOTE (outcome (f)).
    no_file is True when synth_record.json is absent (outcome (a)).
    """

    routes: tuple[SceneTimings | None, ...]
    mismatched: tuple[int, ...]
    no_file: bool
