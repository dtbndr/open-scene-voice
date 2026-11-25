from .common_settings import common_settings
from .job_request import JobRequest
from .project_facts import ProjectFacts


def job_settings(request: JobRequest, facts: ProjectFacts) -> dict[str, str | None]:
    """The voice, model, language and instruction a job runs with (J3).

    Voicing everything uses the creator's; a single scene and the rest use the recorded ones, so one script keeps one
    voice and model. `job_refusal` has already refused a request that disagrees with the record or has none.
    """
    if request.kind == "synth-scene" or request.mode == "rest":
        return common_settings(facts.record.items) or {}
    return {"voice": request.voice, "model": request.model, "language": request.language, "instruction": request.instruction}
