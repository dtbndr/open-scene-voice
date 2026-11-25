from .job_request import JobRequest


def is_beats(request: JobRequest) -> bool:
    """True for the two kinds that run `beats`: the first run and Redo beats."""
    return request.kind in ("beats", "beats-redo")
