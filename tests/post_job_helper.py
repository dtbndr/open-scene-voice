"""A project folder, a fake plan runner, a real runner over the stub CLI and the start handler, for the start-route tests."""

import json
import threading
from pathlib import Path
from typing import Any

from detail_helper import FakePlan, passing, plan_stdout, put_record, put_wavs, sha
from job_runner_helper import make_runner

from scenevoice.web import JobContext, JobEvents, JobRunner, post_job
from scenevoice.web.request import Request
from scenevoice.web.response import Response

BODIES = ["Café one.", "Two \U0001f600 here."]
SCRIPT = b"# One\nCaf\xc3\xa9 one.\n\n# Two\nTwo \xf0\x9f\x98\x80 here.\n"
WAVS = {1: b"wav-one", 2: b"wav-two"}
BODIES3 = [*BODIES, "Three."]
SCRIPT3 = SCRIPT + b"\n# Three\nThree.\n"
MODEL = "gemini-3.8-flash-tts"


def confirm_for(data: bytes = SCRIPT, bodies: list[str] | None = None, model: str = MODEL) -> dict[str, Any]:
    """The numbers the creator was shown for `bodies` (all scenes by default)."""
    chosen = BODIES if bodies is None else bodies
    return {"scenes": len(chosen), "characters": sum(len(body) for body in chosen), "model": model, "revision": sha(data)}


def synth_all(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"kind": "synth", "mode": "all", "voice": "Leda", "model": MODEL, "confirm": confirm_for()}
    return {**body, **changes}


def synth_rest(bodies: list[str] | None = None, **changes: Any) -> dict[str, Any]:
    """Voice the rest: the confirmation counts the UNVOICED scenes (pass their bodies); the model is the recorded one."""
    body: dict[str, Any] = {"kind": "synth", "mode": "rest", "confirm": confirm_for(bodies=bodies if bodies is not None else BODIES[1:])}
    return {**body, **changes}


def synth_restart(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"kind": "synth", "mode": "restart", "voice": "Leda", "model": MODEL, "confirm": confirm_for()}
    return {**body, **changes}


def synth_scene(scene: int = 2, **changes: Any) -> dict[str, Any]:
    bodies = [BODIES[scene - 1]] if scene <= len(BODIES) else BODIES
    body: dict[str, Any] = {"kind": "synth-scene", "scene": scene, "confirm": confirm_for(bodies=bodies)}
    return {**body, **changes}


def align_body(listen: int = len(BODIES), data: bytes = SCRIPT, **changes: Any) -> dict[str, Any]:
    """Align: the confirmation is only the scenes that will be listened to and the revision."""
    return {"kind": "align", "confirm": {"scenes": listen, "revision": sha(data)}, **changes}


PACK_BODY: dict[str, Any] = {"kind": "pack"}
BEATS_MODEL = "openai/gpt-4o-mini"


def beats_body(redo: bool = False, data: bytes = SCRIPT, model: str = BEATS_MODEL, **changes: Any) -> dict[str, Any]:
    """Beats (or Redo beats): the confirmation counts every plan scene and names the OpenRouter model of the request."""
    body: dict[str, Any] = {"kind": "beats-redo" if redo else "beats", "model": model, "confirm": confirm_for(data, model=model)}
    return {**body, **changes}


class JobBed:
    """One workspace holding project `p`, a runner driving `stub`, an event hub and the `post_job` handler for `p`."""

    def __init__(self, stub: Any, tmp_path: Path, run: Any = None, ops: Any = None, **runner_options: Any) -> None:
        self.workspace = tmp_path / "ws"
        self.project = self.workspace / "p"
        self.project.mkdir(parents=True)
        self.runner: JobRunner = make_runner(stub, tmp_path, **runner_options)
        self.launch = tmp_path / "launch"
        self.events = JobEvents()
        self.run: FakePlan = run if run is not None else passing(BODIES)
        self.script_lock = threading.Lock()
        self.stub = stub
        self.ops = ops
        self.context = self.make_context(self.runner, self.events)
        self.handler = post_job(self.context, "p")
        self.other_handler = post_job(self.context, "nobody")

    def make_context(self, runner: JobRunner, events: JobEvents) -> JobContext:
        extra = {"ops": self.ops} if self.ops is not None else {}
        return JobContext(
            lambda: self.workspace, lambda *a, **k: self.run(*a, **k), None, self.launch, threading.Lock(), self.script_lock,
            runner, events, **extra,
        )

    def relaunch(self) -> Any:
        """A new runner, hub and handler over the same folder, as after the server was started again."""
        self.runner = make_runner(self.stub, self.project.parent.parent)
        self.events = JobEvents()
        self.context = self.make_context(self.runner, self.events)
        self.handler = post_job(self.context, "p")
        return self.handler

    def save_script(self, data: bytes = SCRIPT) -> None:
        (self.project / "script.md").write_bytes(data)

    def voice(self, ordinals: tuple[int, ...] = (1, 2)) -> None:
        """Voiced scenes with a Gemini record (voice Leda, `MODEL`, en-GB)."""
        put_wavs(self.project, {n: WAVS[n] for n in ordinals})
        put_record(self.project, BODIES, {n: WAVS[n] for n in ordinals})

    def post(self, body: Any, handler: Any = None) -> tuple[Response, Any]:
        request = Request("POST", "/api/projects/p/jobs", json_body=body)
        response = (handler or self.handler)(request)
        return response, json.loads(response.body)

    def error(self, body: Any) -> tuple[int, str, str]:
        response, parsed = self.post(body)
        return response.status, parsed["error"]["kind"], parsed["error"]["message"]

    def children(self) -> list[dict[str, Any]]:
        return self.stub.calls()

    def launch_files(self) -> list[str]:
        return sorted(path.name for path in self.launch.iterdir())


PLAN_JSON = plan_stdout(BODIES)


class BlockingPlan(FakePlan):
    """A plan runner that stops inside the call until released: a start request held mid-plan."""

    def __init__(self, bodies: list[str] | None = None) -> None:
        super().__init__(passing(BODIES if bodies is None else bodies).result)
        self.entered = threading.Event()
        self.open = threading.Event()

    def __call__(self, args: Any, stdin: Any = None, timeout: float = 30.0) -> Any:
        self.entered.set()
        assert self.open.wait(15)
        return super().__call__(args, stdin, timeout)
