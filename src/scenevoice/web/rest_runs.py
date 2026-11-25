from collections.abc import Mapping
from pathlib import Path

from .build_synth_argv import build_synth_argv
from .planned_scene import PlannedScene


def rest_runs(plan_file: Path, directory: Path, scenes: tuple[PlannedScene, ...], settings: Mapping[str, str | None]) -> list[list[str]]:
    """Voice the rest (J3): one `synth --scene N` argument list per unvoiced scene, in order, over the ONE counted plan file.

    The settings are the record's (never the client's), so one script keeps one voice and model.
    """
    return [
        build_synth_argv(
            plan_file, directory, voice=str(settings["voice"]), model=str(settings["model"]),
            language=settings["language"], instruction=settings["instruction"], scene=scene.ordinal,
        )
        for scene in scenes
    ]
