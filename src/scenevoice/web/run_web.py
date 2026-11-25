import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .absolute_keys_file import absolute_keys_file
from .bind_runner import bind_runner
from .bind_socket import bind_socket
from .build_allowlist import build_allowlist
from .chain_routes import chain_routes
from .child_env import child_env
from .ensure_index import ensure_index
from .get_catalog import get_catalog
from .ignored_environment import ignored_environment
from .job_events import JobEvents
from .job_runner import JobRunner
from .key_file_overlap import key_file_overlap
from .launch_message import launch_message
from .make_gate import make_gate
from .make_launch_dir import make_launch_dir
from .make_link import make_link
from .make_root_getter import make_root_getter
from .make_server import make_server
from .make_token import make_token
from .open_browser import open_browser
from .port_busy_error import PortBusyError
from .print_stopped import print_stopped
from .project_routes import ProjectRoutes
from .quiet_server import QuietServer
from .register_job_routes import register_job_routes
from .register_keys_routes import register_keys_routes
from .remove_launch_dir import remove_launch_dir
from .resolve_workspace import resolve_workspace
from .run_opener import Launch, run_opener
from .serve_static import serve_static
from .serve_until_stopped import serve_until_stopped
from .stop_signals import StopSignals
from .workspace_error import KEY_FILE_MESSAGE, WorkspaceError


def run_web(
    *,
    port: int,
    no_open: bool,
    opener: Callable[[str], object],
    environ: Mapping[str, str],
    serve: Callable[[QuietServer], None] = serve_until_stopped,
    prefix: Sequence[str] | None = None,
    workspace: Path | None = None,
    launch: Launch = run_opener,
    key_file: Path | None = None,
) -> int:
    """Assemble and run the local web server; the single place later workstreams add routes.

    Order matters: bind first (a busy port prints and leaves nothing), create the launch directory only after
    the bind, and print the link only once the socket is ours so no other program ever receives the token.
    The workspace is only checked lexically here (absolute, and not holding `key_file`); `key_file=None` means no
    check, and only `cli/web.py` computes it. `launch` starts the reveal program (default: the real `run_opener`; tests pass a recorder).
    """
    try:
        workspace_path = resolve_workspace(environ, workspace)
        if key_file is not None and key_file_overlap(workspace_path, key_file):
            raise WorkspaceError(KEY_FILE_MESSAGE)
    except WorkspaceError as error:
        print(f"scenevoice web: {error}", file=sys.stderr)
        return 1
    try:
        allowlist = ensure_index(build_allowlist())
        sock = bind_socket(port)
    except PortBusyError as error:
        print(f"scenevoice web: {error}", file=sys.stderr)
        return 1
    launch_dir = make_launch_dir()
    server: QuietServer | None = None
    runner: JobRunner | None = None
    events = JobEvents()
    signals = StopSignals()
    interrupted = False
    try:
        signals.install()
        token = make_token()
        bound_port = sock.getsockname()[1]
        ignored = ignored_environment(environ)
        child_environment = child_env(absolute_keys_file(environ))
        runner = JobRunner(cwd=launch_dir, env=child_environment, prefix=prefix)
        routes = register_keys_routes(cwd=launch_dir, environ=environ, ignored_environment=ignored, prefix=prefix)
        jobs = register_job_routes(runner, events)
        projects = ProjectRoutes(
            root_getter=make_root_getter(workspace_path, key_file),
            run=bind_runner(launch_dir, child_environment, prefix),
            key_file=key_file,
            launch=launch,
            launch_dir=launch_dir,
            job_active=runner.job_active,
            runner=runner,
            events=events,
        )
        server = make_server(
            sock, chain_routes(chain_routes(chain_routes(routes, jobs), get_catalog()), projects), make_gate(token, bound_port), static=lambda request: serve_static(request, allowlist)
        )
        link = make_link(bound_port, token)
        for line in launch_message(link, ignored):
            print(line, flush=True)
        if not no_open:
            open_browser(opener, link)
        serve(server)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        try:
            signals.latch()  # a signal now must not cut the cleanup short: the handlers stay latched until the end
            if runner is not None:
                runner.shutdown()  # first: the child and its group are gone before the socket and the directory are
            events.close()  # wakes the open event streams so their handler threads end
            if server is not None:
                server.server_close()
            else:
                sock.close()
            remove_launch_dir(launch_dir)
            if interrupted:
                print_stopped()
        finally:
            signals.restore()
    return 0
