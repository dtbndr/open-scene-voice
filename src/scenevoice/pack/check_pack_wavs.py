from pathlib import Path

from scenevoice.synth import PlanScene, load_scene_wavs


def check_pack_wavs(
    scenes: list[PlanScene], directory: str | Path, min_frames: int = 0
) -> list[int] | str:
    """Check 4: frame counts per scene in plan order, or a one-line message for the first failure.

    A thin wrapper over the shared synth loader; min_frames is the editor run's zero-frame rule (0 turns it off).
    """
    result = load_scene_wavs(scenes, directory, min_frames)
    if isinstance(result, str):
        return result
    return [wav.frames for wav in result]
