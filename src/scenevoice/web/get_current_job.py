from urllib.parse import parse_qsl

from .current_job_json import current_job_json
from .error_envelope import error_envelope
from .job_events import JobEvents
from .job_runner import JobRunner
from .json_response import json_response
from .request import Request
from .response import Response
from .route_table import Handler
from .run_id import is_run_id


def get_current_job(runner: JobRunner, hub: JobEvents) -> Handler:
    """GET /api/jobs/current: the last result or the running job; reads only.

    `?run=<id>` answers that run (live, else its retained final with its own failure), 404 when unknown and 400
    when the id is malformed.
    """

    def handle(request: Request) -> Response:
        runs = [value for key, value in parse_qsl(request.query, keep_blank_values=True) if key == "run"]
        if not runs:
            return json_response(200, current_job_json(runner.current(), hub.latest_events()))
        if len(runs) != 1 or not is_run_id(runs[0]):
            return error_envelope("bad_request", "That run id is not valid.")
        found = runner.lookup(runs[0])
        if found is None:
            return error_envelope("not_found", "No such run.")
        return json_response(200, current_job_json(found[0], [], found[1]))

    return handle
