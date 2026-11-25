from .job_availability import job_availability
from .project_facts import ProjectFacts


def can_flags(facts: ProjectFacts) -> dict[str, object]:
    """The `can` object of the project detail: a flag per kind and mode, each `job_availability` answering None."""

    def allowed(kind: str, mode: str | None = None) -> bool:
        return job_availability(facts, kind, mode) is None

    return {
        "synth": {"all": allowed("synth", "all"), "rest": allowed("synth", "rest"), "restart": allowed("synth", "restart")},
        "synth_scene": allowed("synth-scene"),
        "align": allowed("align"),
        "beats": allowed("beats"),
        "beats_redo": allowed("beats-redo"),
        "pack": allowed("pack"),
    }
