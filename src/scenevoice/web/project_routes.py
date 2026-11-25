import re
import threading
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path

from .check_script import check_script
from .cli_result import CliResult
from .get_beats import get_beats
from .get_pack_zip import get_pack_zip
from .get_project_detail import get_project_detail
from .get_projects import get_projects
from .get_script import get_script
from .is_project_id import PROJECT_ID_PATTERN
from .job_context import JobContext
from .job_events import JobEvents
from .job_runner import JobRunner
from .post_job import post_job
from .post_projects import post_projects
from .post_reveal import post_reveal
from .put_script import put_script
from .route_table import Handler
from .run_opener import Launch
from .serve_audio import serve_audio

# (compiled pattern, factory(routes, id, file) -> methods). The ONE place a route shape is added: later slices append
# a row; the pattern is `fullmatch`ed against the raw path and may name the groups `id` and `file`.
ID = f"(?P<id>{PROJECT_ID_PATTERN})"
Factory = Callable[["ProjectRoutes", str | None, str | None], dict[str, Handler]]


def _collection(routes: "ProjectRoutes", project_id: str | None, file: str | None) -> dict[str, Handler]:
    return {"GET": get_projects(routes.root_getter), "POST": post_projects(routes.root_getter)}


def _detail(routes: "ProjectRoutes", project_id: str | None, file: str | None) -> dict[str, Handler]:
    assert project_id is not None
    return {
        "GET": get_project_detail(
            routes.root_getter, project_id, routes.key_file, routes.run, routes.launch_dir, routes.check_lock, routes.job_active
        )
    }


def _jobs(routes: "ProjectRoutes", project_id: str | None, file: str | None) -> dict[str, Handler]:
    assert project_id is not None
    return {"POST": post_job(routes.job_context(), project_id)}


def _script(routes: "ProjectRoutes", project_id: str | None, file: str | None) -> dict[str, Handler]:
    assert project_id is not None
    return {
        "GET": get_script(routes.root_getter, project_id, routes.key_file),
        "PUT": put_script(routes.root_getter, project_id, routes.key_file, routes.runner, routes.script_lock),
    }


def _beats(routes: "ProjectRoutes", project_id: str | None, file: str | None) -> dict[str, Handler]:
    assert project_id is not None
    return {"GET": get_beats(routes.root_getter, project_id, routes.key_file)}


def _check(routes: "ProjectRoutes", project_id: str | None, file: str | None) -> dict[str, Handler]:
    assert project_id is not None
    return {"POST": check_script(routes.root_getter, project_id, routes.run, routes.launch_dir, routes.check_lock)}


def _audio(routes: "ProjectRoutes", project_id: str | None, file: str | None) -> dict[str, Handler]:
    assert project_id is not None and file is not None
    return {"GET": serve_audio(routes.root_getter, project_id, file, routes.key_file)}


def _pack(routes: "ProjectRoutes", project_id: str | None, file: str | None) -> dict[str, Handler]:
    assert project_id is not None
    return {"GET": get_pack_zip(routes.root_getter, project_id, routes.key_file, routes.runner)}


def _reveal(routes: "ProjectRoutes", project_id: str | None, file: str | None) -> dict[str, Handler]:
    assert project_id is not None
    return {"POST": post_reveal(routes.root_getter, project_id, routes.launch, routes.platform)}


SHAPES: tuple[tuple[re.Pattern[str], Factory], ...] = (
    (re.compile(r"/api/projects"), _collection),
    (re.compile(f"/api/projects/{ID}"), _detail),
    (re.compile(f"/api/projects/{ID}/beats"), _beats),
    (re.compile(f"/api/projects/{ID}/jobs"), _jobs),
    (re.compile(f"/api/projects/{ID}/script"), _script),
    (re.compile(f"/api/projects/{ID}/check"), _check),
    (re.compile(f"/api/projects/{ID}/audio/(?P<file>[^/]+)"), _audio),  # the name allowlist is audio_file_name's
    (re.compile(f"/api/projects/{ID}/pack\\.zip"), _pack),
    (re.compile(f"/api/projects/{ID}/reveal"), _reveal),
)


class ProjectRoutes(Mapping[str, Mapping[str, Handler]]):
    """Route table for the project API: raw path -> methods, built from fixed shapes with the id bound in.

    `dispatch` only calls `get` and `in`, so iteration is empty by design; `get` is inherited from `Mapping`.
    The class never touches the filesystem: a valid id with no folder is answered by the handler.
    """

    def __init__(
        self,
        *,
        root_getter: Callable[[], Path],
        run: Callable[..., CliResult],
        key_file: Path | None,
        launch: Launch,
        launch_dir: Path,
        job_active: Callable[[], bool],
        runner: JobRunner,
        events: JobEvents,
        platform: str | None = None,
    ) -> None:
        self.root_getter = root_getter
        self.run = run
        self.key_file = key_file
        self.launch = launch
        self.launch_dir = launch_dir
        self.platform = platform  # None: `sys.platform` at each call
        self.job_active = job_active  # True while a job holds the slot (the detail hides `kept_backups` then)
        self.runner = runner
        self.events = events
        self.check_lock = threading.Lock()  # per server: ProjectRoutes is built once per server
        self.script_lock = threading.Lock()  # lock order: the job slot, then this, then check_lock; never reversed

    def job_context(self) -> JobContext:
        return JobContext(
            self.root_getter, self.run, self.key_file, self.launch_dir, self.check_lock, self.script_lock, self.runner, self.events
        )

    def __getitem__(self, path: str) -> Mapping[str, Handler]:
        for pattern, factory in SHAPES:
            found = pattern.fullmatch(path)
            if found:
                groups = found.groupdict()
                return factory(self, groups.get("id"), groups.get("file"))
        raise KeyError(path)

    def __iter__(self) -> Iterator[str]:
        return iter(())

    def __len__(self) -> int:
        return 0
