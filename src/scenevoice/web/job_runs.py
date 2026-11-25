from collections.abc import Sequence
from pathlib import Path

from .build_align_argv import build_align_argv
from .build_beats_argv import build_beats_argv
from .build_pack_argv import build_pack_argv
from .build_synth_argv import build_synth_argv
from .is_beats import is_beats
from .job_request import JobRequest
from .job_settings import job_settings
from .planned_scene import PlannedScene
from .project_facts import ProjectFacts
from .rest_runs import rest_runs


def job_runs(
    request: JobRequest, plan_file: Path, directory: Path, scenes: Sequence[PlannedScene], facts: ProjectFacts,
    candidate: Path | None = None,
) -> list[list[str]]:
    """The CLI runs of a job, each over the one counted plan file: align and pack one run each, `rest` one per scene, else one `synth`.

    Beats is the exception: its one run reads the private copy of the counted script (`plan_file` is that copy) and writes the `candidate`.
    """
    if is_beats(request) and candidate is not None:
        return [build_beats_argv(plan_file, candidate, str(request.model))]
    if request.kind == "align":
        return [build_align_argv(plan_file, directory)]
    if request.kind == "pack":
        return [build_pack_argv(plan_file, directory)]
    settings = job_settings(request, facts)
    if request.mode == "rest":
        return rest_runs(plan_file, directory, tuple(scenes), settings)
    return [build_synth_argv(
        plan_file, directory, voice=str(settings["voice"]), model=str(settings["model"]),
        language=settings["language"], instruction=settings["instruction"], scene=request.scene,
    )]
