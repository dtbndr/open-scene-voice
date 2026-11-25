import functools
import os
from collections.abc import Callable
from pathlib import Path

from .beats_start import BeatsStart
from .current_job_json import current_job_json
from .job_context import JobContext
from .job_mode import job_mode
from .job_request import JobRequest
from .job_runs import job_runs
from .job_scenes import job_scenes
from .job_spec import JobSpec
from .json_response import json_response
from .plan_run import PlanRun
from .project_facts import ProjectFacts
from .response import Response
from .scrub_text import scrub_text
from .slot_handle import SlotHandle
from .slot_refused import SlotRefused
from .start_refused import start_refused
from .write_private_file import write_private_file


def launch_job(
    context: JobContext, directory: Path, root: Path, project_id: str, request: JobRequest, plan: PlanRun,
    facts: ProjectFacts, handle: SlotHandle, on_finish: Callable[[str, int], tuple[str | None, str | None]] | None,
    beats: BeatsStart | None = None,
) -> Response:
    """Write the counted plan, build the runs and start the child (J2 steps 9 and 10); the plan file goes if it never started.

    `beats` hands the child the counted script bytes in a private copy instead of the plan (the sidecar's hash is then
    the hash of what was confirmed) and its candidate path to write.
    """
    runner = context.runner
    if beats is None:
        plan_file = write_private_file(context.launch_dir, "plan-", ".json", plan.stdout)
    else:
        plan_file = write_private_file(context.launch_dir, "script-", ".md", beats.script)
    started = False
    try:
        scenes = job_scenes(request, plan.scenes, facts)
        runs = job_runs(request, plan_file, directory, scenes, facts, beats.candidate if beats else None)
        scrub = functools.partial(
            scrub_text, project_dir=directory, project_id=project_id, launch_dir=context.launch_dir,
            workspace=root, key_file=context.key_file,
        )
        observer = context.events.observer(scrub=scrub, on_scene_done=runner.note_scene_done)
        spec = JobSpec(
            request.kind, job_mode(request), project_id, runs, len(scenes), request.scene,
            cleanup=(plan_file,), on_finish=on_finish, observer=observer,
        )
        try:
            runner.start(handle, spec)
        except SlotRefused:
            return start_refused(runner)
        started = True
        observer.flush()  # opens the job's event buffer now, so a silent child still has a job number
        found = runner.lookup(handle.run)  # this run's own status, even if it has already ended
        status, failure = found if found is not None else (runner.current(), None)
        return json_response(202, current_job_json(status, [], failure))
    finally:
        if not started:
            _unlink(plan_file)


def _unlink(path: Path) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass
