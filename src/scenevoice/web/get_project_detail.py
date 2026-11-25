import threading
from collections.abc import Callable
from pathlib import Path

from .can_flags import can_flags
from .check_script import CHECK_FAILED
from .cli_result import CliResult
from .describe_audio import describe_audio
from .describe_line_markers import describe_line_markers
from .describe_script import describe_script
from .error_envelope import error_envelope
from .json_response import json_response
from .plan_problem import PlanProblem
from .plan_run import PlanRun
from .project_dir import project_dir
from .read_project_facts import read_project_facts
from .read_script_bytes import read_script_bytes
from .regular_file import regular_file
from .request import Request
from .response import Response
from .route_table import Handler
from .run_plan import run_plan
from .scan_backups import scan_backups
from .script_bytes import ScriptBytes
from .with_root import with_root


def _script_state(script: ScriptBytes, plan: PlanRun | PlanProblem | None) -> str:
    if isinstance(plan, PlanRun):
        return "ok"
    return "problem" if script.problem is not None or plan is not None else "none"


def _read(
    directory: Path, key_file: Path | None, run: Callable[..., CliResult], launch_dir: Path, lock: threading.Lock, job_active: Callable[[], bool]
) -> Response:
    script = read_script_bytes(directory, key_file)
    plan = None
    if script.data is not None and script.problem is None:
        plan = run_plan(script.data, run, launch_dir, lock)
        if plan is None:
            return error_envelope("cli_failed", CHECK_FAILED)
    description = describe_script(script, plan)
    scenes = plan.scenes if isinstance(plan, PlanRun) else ()
    revision = description["revision"]
    assert revision is None or isinstance(revision, str)
    facts = read_project_facts(directory, key_file, _script_state(script, plan), scenes, revision)
    return json_response(
        200,
        {
            "script": description,
            "audio": describe_audio(scenes, facts.audio, facts.record, facts.timings),
            "line_markers": describe_line_markers(scenes, facts.audio, facts.record, facts.timings),
            "beats": {"state": facts.beats},
            "pack": {
                "manifest": regular_file(directory, "scene_manifest.csv", key_file=key_file) is not None,
                "timeline": regular_file(directory, "resolve_timeline.otio", key_file=key_file) is not None,
            },
            "kept_backups": None if job_active() else scan_backups(directory),
            "can": can_flags(facts),
        },
    )


def get_project_detail(
    root_getter: Callable[[], Path],
    project_id: str,
    key_file: Path | None,
    run: Callable[..., CliResult],
    launch_dir: Path,
    lock: threading.Lock,
    job_active: Callable[[], bool],
) -> Handler:
    """GET /api/projects/{id}: everything the screen needs from disk, plus `plan` once on the saved script; writes nothing.

    The plan runs through the shared check lock (a detail GET and a check serialise, 10 s cap). `kept_backups` is null
    while a job holds the slot. Titles and messages are creator text: JSON only.
    """

    def handle(request: Request) -> Response:
        def use(root: Path) -> Response:
            directory = project_dir(root, project_id)
            if directory is None:
                return error_envelope("not_found", "That project does not exist.")
            return _read(directory, key_file, run, launch_dir, lock, job_active)

        return with_root(root_getter, use)

    return handle
