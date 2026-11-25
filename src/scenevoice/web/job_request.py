from dataclasses import dataclass

UNKNOWN_JOB = "Send a job the server knows."


@dataclass(frozen=True)
class JobRequest:
    """A start request that passed `parse_job_request`: its shape is right, nothing about the project is checked yet."""

    kind: str
    mode: str | None = None
    scene: int | None = None
    voice: str | None = None
    model: str | None = None
    language: str | None = None
    instruction: str | None = None
    confirm: dict[str, object] | None = None
