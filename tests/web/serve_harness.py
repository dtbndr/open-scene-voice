"""A real `run_web` in its own process for the shutdown tests; run as `python serve_harness.py CONFIG.json`.

The test starts it with `subprocess.Popen` (never a shell `&`) and sends it real signals. Config keys:
`prefix` (the stub CLI argv prefix), `workspace`, `kill_delay`, `ready` (file written once the job's child is
running), `result` (JSON written when the launch directory is about to be removed: whether the child and its group
were already gone) and `job` (start one job whose child is the stub).
"""

import json
import os
import sys
import time
from pathlib import Path

from scenevoice.web import JobSpec, run_web

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
module = sys.modules["scenevoice.web.run_web"]
captured: dict[str, object] = {}
real_runner = module.JobRunner
real_remove = module.remove_launch_dir


def runner_factory(**options):
    runner = real_runner(**{**options, "kill_delay": config["kill_delay"], "shutdown_bound": 20.0})
    captured["runner"] = runner
    return runner


def gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def group_gone(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def remove_launch_dir(path):
    pid = captured.get("pid")
    deadline = time.monotonic() + 5.0  # a killed grandchild is reaped by init a moment after the kill
    while pid is not None and not group_gone(pid) and time.monotonic() < deadline:
        time.sleep(0.01)
    Path(config["result"]).write_text(
        json.dumps(
            {
                "child_gone": pid is None or gone(pid),
                "group_gone": pid is None or group_gone(pid),
                "launch_dir_existed": Path(path).exists(),
            }
        ),
        encoding="utf-8",
    )
    real_remove(path)


def wait_for(path: str, seconds: float = 20.0) -> None:
    deadline = time.monotonic() + seconds
    while not Path(path).exists() and time.monotonic() < deadline:
        time.sleep(0.01)


def serve(server) -> None:
    runner = captured["runner"]
    if config.get("job"):
        handle = runner.reserve("synth", "p")
        runner.start(handle, JobSpec(kind="synth", mode="all", project="p", runs=[["synth", "1"]], total=1))
        events = Path(config["prefix"][-1]).with_name("recording.json")
        wait_for(str(events))
        captured["pid"] = json.loads(events.read_text(encoding="utf-8"))["pid"]
    Path(config["ready"]).write_text("ready", encoding="utf-8")
    while True:
        time.sleep(0.05)


module.JobRunner = runner_factory
module.remove_launch_dir = remove_launch_dir
sys.exit(
    run_web(
        port=0,
        no_open=True,
        opener=lambda link: True,
        environ={},
        serve=serve,
        prefix=config["prefix"],
        workspace=Path(config["workspace"]),
    )
)
