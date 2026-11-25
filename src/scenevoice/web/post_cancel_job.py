from .error_envelope import error_envelope
from .job_runner import JobRunner
from .job_state import NOTHING, STALE
from .json_response import json_response
from .request import Request
from .response import Response
from .route_table import Handler
from .run_id import is_run_id

NEEDS_RUN = "Say which run to stop."
# Proposed wording (owner gate): the shared `changed` text in job_refusal is about a start, so cancel has its own.
ENDED = "That voicing run has already ended, so nothing was stopped."


def post_cancel_job(runner: JobRunner) -> Handler:
    """POST /api/jobs/current/cancel `{"run"}`: stop that run only (idempotent while it is stopping).

    400 without a well-formed run id, 404 when no job holds the slot, 409 `changed` when another run holds it.
    """

    def handle(request: Request) -> Response:
        body = request.json_body
        run = body.get("run") if isinstance(body, dict) else None
        if not is_run_id(run):
            return error_envelope("bad_request", NEEDS_RUN)
        outcome = runner.cancel_run(str(run))
        if outcome == NOTHING:
            return error_envelope("not_found", "Nothing is running.")
        if outcome == STALE:
            return error_envelope("changed", ENDED)
        return json_response(200, {"cancelling": True})

    return handle
