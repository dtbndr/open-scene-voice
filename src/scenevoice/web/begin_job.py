from pathlib import Path

from .beats_start import BeatsStart
from .begin_beats import begin_beats
from .busy_message import busy_message
from .check_script import CHECK_FAILED
from .clear_pack_outputs import clear_pack_outputs
from .error_envelope import error_envelope
from .is_beats import is_beats
from .job_context import JobContext
from .job_refusal import job_refusal
from .job_request import JobRequest
from .launch_job import launch_job
from .not_ordinary import NotOrdinary
from .plan_problem import PlanProblem
from .read_project_facts import read_project_facts
from .read_script_bytes import read_script_bytes
from .response import Response
from .restart_hook import restart_hook
from .restart_messages import NOT_ORDINARY, ROLLBACK_FAILED, WENT_WRONG
from .restore_set_aside import restore_set_aside
from .run_plan import run_plan
from .set_aside import SetAside, SetAsideFailed
from .set_aside_files import set_aside_files
from .start_refused import start_refused

SAVE_FIRST = "Save a script first."
FIX_FIRST = "Fix the problems in your script first."


def begin_job(context: JobContext, directory: Path, root: Path, project_id: str, request: JobRequest) -> Response:
    """Reserve the slot, read and plan the script once, check the echo, and start the child on exactly those bytes.

    The slot is reserved BEFORE `script.md` is read and given back by the one `finally` here on every path that does
    not reach `start` (a no-op after it). Lock order: slot, script lock, check lock (inside `run_plan`), never reversed.
    Start again sets its files aside only after every check has passed and only while the slot is still valid, and
    puts them back on any exit before the child has started.
    """
    runner = context.runner
    handle = runner.reserve(request.kind, project_id)
    if handle is None:
        return error_envelope("busy", busy_message(runner.busy_reason()))
    try:
        with context.script_lock:
            script = read_script_bytes(directory, context.key_file)
        if script.data is None and script.problem is None:
            return error_envelope("not_allowed", SAVE_FIRST)
        if script.data is None or script.problem is not None:
            return error_envelope("not_allowed", FIX_FIRST)
        plan = run_plan(script.data, context.run, context.launch_dir, context.check_lock)
        if plan is None:
            return error_envelope("cli_failed", CHECK_FAILED)
        if isinstance(plan, PlanProblem):
            return error_envelope("not_allowed", FIX_FIRST)
        facts = read_project_facts(directory, context.key_file, "ok", plan.scenes, plan.revision)
        refusal = job_refusal(request, plan, script.data, facts)
        if refusal is not None:
            return refusal
        if request.kind == "pack":
            cleared = clear_pack_outputs(context, directory, handle)
            if cleared is not None:
                return cleared
        beats: BeatsStart | None = None
        if is_beats(request):
            prepared = begin_beats(context, directory, handle, request, script.data, plan.revision)
            if isinstance(prepared, Response):
                return prepared
            beats = prepared
        aside: SetAside | None = None
        if request.mode == "restart":
            if not runner.valid(handle):  # a cancel or shutdown during the plan: nothing may be moved
                return start_refused(runner)
            try:
                aside = set_aside_files(directory, context.key_file, context.ops)
            except NotOrdinary:
                return error_envelope("not_allowed", NOT_ORDINARY)
            except SetAsideFailed as failed:
                put_back = restore_set_aside(failed.done, context.ops)
                return error_envelope("internal_error", ROLLBACK_FAILED if put_back == "failed" else WENT_WRONG)
        hook = restart_hook(aside, directory, context.key_file, context.ops) if aside is not None else None
        if beats is not None:
            hook = beats.hook
        failure: Exception | None = None
        try:
            response = launch_job(context, directory, root, project_id, request, plan, facts, handle, hook, beats)
        except Exception as error:  # re-raised below, after the old files are back
            failure = error
        if aside is not None and not handle.started and restore_set_aside(aside, context.ops) == "failed":
            return error_envelope("internal_error", ROLLBACK_FAILED)
        if failure is not None:
            raise failure
        return response
    finally:
        runner.release(handle)
