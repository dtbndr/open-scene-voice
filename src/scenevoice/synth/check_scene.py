from scenevoice.validation import Violation

_RULE = "scene"


def check_scene(scene: int, scene_count: int) -> Violation | None:
    """`--scene N` must name a scene of the plan (1-based)."""
    if 1 <= scene <= scene_count:
        return None
    return Violation(
        _RULE, f"--scene {scene} is out of range (the plan has {scene_count} scenes)"
    )
