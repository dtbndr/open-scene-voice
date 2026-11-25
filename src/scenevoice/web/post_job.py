from pathlib import Path

from .begin_job import begin_job
from .error_envelope import error_envelope
from .job_context import JobContext
from .job_request import UNKNOWN_JOB
from .parse_job_request import parse_job_request
from .project_dir import project_dir
from .request import Request
from .response import Response
from .route_table import Handler
from .with_root import with_root

# The ONE place a kind is made startable: later slices add their (kind, mode) here; any other kind that parses is
# answered "Send a job the server knows." until then.
STARTABLE = {
    ("synth", "all"), ("synth", "rest"), ("synth", "restart"), ("synth-scene", None), ("align", None), ("pack", None),
    ("beats", None), ("beats-redo", None),
}


def post_job(context: JobContext, project_id: str) -> Handler:
    """POST /api/projects/{id}/jobs: one start, in the order of J2 (body, project, slot, script, plan, echo, spawn).

    The body is judged before the project is looked up (WS42 convention). The rest happens in `begin_job`, which
    holds the job slot from before `script.md` is read until the job is started or the request is refused.
    """

    def handle(request: Request) -> Response:
        job = parse_job_request(request.json_body)
        if job is None or (job.kind, job.mode) not in STARTABLE:
            return error_envelope("bad_request", UNKNOWN_JOB)

        def use(root: Path) -> Response:
            directory = project_dir(root, project_id)
            if directory is None:
                return error_envelope("not_found", "That project does not exist.")
            return begin_job(context, directory, root, project_id, job)

        return with_root(context.root_getter, use)

    return handle
