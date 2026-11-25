from .job_request import JobRequest
from .planned_scene import PlannedScene
from .project_facts import ProjectFacts


def job_scenes(request: JobRequest, scenes: tuple[PlannedScene, ...], facts: ProjectFacts) -> tuple[PlannedScene, ...]:
    """The plan scenes a job will voice (J1): scene N alone, the unvoiced ones for `rest`, else all of them."""
    if request.kind == "synth-scene":
        return tuple(scene for scene in scenes if scene.ordinal == request.scene)
    if request.kind == "synth" and request.mode == "rest":
        return tuple(scene for scene in scenes if scene.ordinal not in facts.audio.hashes)
    return scenes
