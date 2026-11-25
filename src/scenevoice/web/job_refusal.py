from .align_echo import align_echo
from .common_settings import common_settings
from .error_envelope import error_envelope
from .job_availability import job_availability
from .job_echo import job_echo
from .job_request import JobRequest
from .job_scenes import job_scenes
from .plan_run import PlanRun
from .project_facts import ProjectFacts
from .response import Response

CHANGED = "The script or settings changed since you confirmed. Check the numbers and confirm again."
_SETTINGS = ("voice", "model", "language", "instruction")


def job_refusal(request: JobRequest, plan: PlanRun, data: bytes, facts: ProjectFacts) -> Response | None:
    """The refusal for a start whose script is planned: `changed` (a scene gone from the plan, or numbers that differ), then `not_allowed`; else None.

    The echo (J1) is recomputed from the bytes that were planned, and is compared before availability, so a
    stale confirmation is always `changed` first. The scenes the job voices are all of them, the unvoiced ones
    (`rest`) or scene N alone. A model left out of a scene or rest request is the recorded one; with no recorded
    one the creator's own is compared (availability then refuses the missing record).
    """
    scenes = job_scenes(request, plan.scenes, facts)
    if request.kind == "synth-scene" and not scenes:  # the scene is gone from the script: a stale tab, whatever the numbers it sends
        return error_envelope("changed", CHANGED)
    confirm = request.confirm or {}
    recorded = common_settings(facts.record.items) or {}
    model = request.model or recorded.get("model") or str(confirm.get("model"))
    echo = align_echo(facts, data) if request.kind == "align" else job_echo(scenes, model, data)
    if request.kind != "pack" and confirm != echo:  # pack is free and carries no confirmation
        return error_envelope("changed", CHANGED)
    supplied = {name: getattr(request, name) for name in _SETTINGS if getattr(request, name) is not None}
    from_record = request.kind == "synth-scene" or request.mode == "rest"
    refusal = job_availability(facts, request.kind, request.mode, supplied if from_record else None)
    return error_envelope("not_allowed", refusal) if refusal is not None else None
