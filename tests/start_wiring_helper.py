"""A real loopback server over the keys-free project and job routes, a real runner and the stub CLI, for the start wiring test."""

import os
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from job_runner_helper import make_runner
from job_wiring_helper import JobsServer
from project_routes_helper import make_project_routes

from scenevoice.web import (
    JobEvents,
    bind_runner,
    chain_routes,
    make_gate,
    make_root_getter,
    make_server,
    make_token,
    register_job_routes,
)


@contextmanager
def running_start_server(stub: Any, tmp_path: Path) -> Iterator[JobsServer]:
    """Workspace `tmp_path/ws`, launch directory `tmp_path/launch`; plans and jobs both run the stub."""
    runner = make_runner(stub, tmp_path)
    launch = tmp_path / "launch"
    hub = JobEvents()
    projects = make_project_routes(
        root_getter=make_root_getter(tmp_path / "ws", None),
        run=bind_runner(launch, dict(os.environ), stub.prefix),
        launch_dir=launch,
        job_active=runner.job_active,
        runner=runner,
        events=hub,
    )
    routes = chain_routes(register_job_routes(runner, hub, keepalive=0.2), projects)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    token = make_token()
    server = make_server(sock, routes, make_gate(token, port), timeout=5.0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield JobsServer(port, token, runner, hub)
    finally:
        runner.shutdown()
        hub.close()
        server.shutdown()
        server.server_close()
        thread.join(5)
