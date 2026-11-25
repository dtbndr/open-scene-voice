from .get_current_job import get_current_job
from .get_job_events import get_job_events
from .job_events import JobEvents
from .job_runner import JobRunner
from .post_cancel_job import post_cancel_job
from .route_table import Handler


def register_job_routes(
    runner: JobRunner, hub: JobEvents, *, keepalive: float = 15.0, poll: float = 0.5
) -> dict[str, dict[str, Handler]]:
    """The three fixed job paths; one call per server. `keepalive` and `poll` (seconds) are injectable for tests."""
    return {
        "/api/jobs/current": {"GET": get_current_job(runner, hub)},
        "/api/jobs/current/events": {"GET": get_job_events(runner, hub, keepalive, poll)},
        "/api/jobs/current/cancel": {"POST": post_cancel_job(runner)},
    }
