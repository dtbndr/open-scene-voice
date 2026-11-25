from .busy_message import busy_message
from .error_envelope import error_envelope
from .job_runner import JobRunner
from .response import Response

CANCELLED = "Cancelled before it started. Nothing was spent."


def start_refused(runner: JobRunner) -> Response:
    """The 409 for a start whose slot was cancelled (or closed by the shutdown) before the child could be spawned."""
    return error_envelope("busy", busy_message("stopping") if runner.busy_reason() == "stopping" else CANCELLED)
