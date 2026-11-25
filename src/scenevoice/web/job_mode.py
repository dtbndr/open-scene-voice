from .job_request import JobRequest


def job_mode(request: JobRequest) -> str:
    """The machine value the job reports as its `mode`: the synth mode, `scene` for one scene, else the kind itself (align, pack, beats)."""
    if request.mode is not None:
        return request.mode
    return "scene" if request.kind == "synth-scene" else request.kind
