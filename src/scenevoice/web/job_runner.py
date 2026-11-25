import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from .cli_argv_prefix import cli_argv_prefix
from .job_spec import JobSpec
from .job_state import CANCELLING, NOTHING, RUNNING, STALE, STARTING, STOPPED, JobStatus
from .retained_finals import RetainedFinals, RunLookup
from .run_job import run_job
from .running_child import RunningChild
from .scene_counter import SceneCounter
from .slot_handle import SlotHandle
from .slot_refused import SlotRefused
from .spawn_run import spawn_run
from .stdout_capture import StdoutCapture
from .stop_process_group import stop_process_group
from .zip_admission import ZipAdmission

_LIVE = (STARTING, RUNNING, CANCELLING)


class JobRunner:
    """The per-server owner of the single job slot, its one child at a time, and the zip admissions beside it.

    One lock guards everything. The slot is held from `reserve` to the owner's `release`, or, once `start` has
    consumed the handle, until the job thread has finished the hooks and the cleanup. Zip downloads share the slot
    with each other and exclude jobs. The runner parses no output: raw stderr lines go to the spec's observer.
    """

    def __init__(
        self,
        *,
        cwd: Path,
        env: Mapping[str, str],
        prefix: Sequence[str] | None = None,
        kill_delay: float = 5.0,
        shutdown_bound: float = 30.0,
    ) -> None:
        self._cwd = cwd
        self._env = dict(env)
        self._prefix = list(prefix) if prefix is not None else None
        self._kill_delay = kill_delay
        self._bound = shutdown_bound
        self._cond = threading.Condition()
        self._handle: SlotHandle | None = None
        self._admissions = 0
        self._closed = False
        self._status = JobStatus()
        self._before_reserve = JobStatus()  # the last result, given back when a reservation never starts
        self._child: RunningChild | None = None
        self._cancel = False
        self._hooks = False
        self._runs_completed = 0
        self._multi = False
        self._retained = RetainedFinals()
        self._stoppers: list[threading.Thread] = []
        self._thread: threading.Thread | None = None
        self._counter = SceneCounter()
        self._stdout = StdoutCapture(b"", 0)

    def reserve(self, kind: str, project: str) -> SlotHandle | None:
        """A handle for the slot, or None while a job, a reservation, a download or the shutdown holds it."""
        with self._cond:
            if self._closed or self._handle is not None or self._admissions:
                return None
            self._handle = SlotHandle(kind, project)
            self._before_reserve = self._status
            self._status = JobStatus(state=STARTING, kind=kind, project=project, run=self._handle.run)
            self._cancel = self._hooks = False
            self._runs_completed = 0
            return self._handle

    def start(self, handle: SlotHandle, spec: JobSpec) -> None:
        """Consume `handle` and run `spec` on a job thread; `SlotRefused` if the handle is no longer usable."""
        with self._cond:
            if handle is not self._handle or handle.started or handle.released or handle.refused:
                raise SlotRefused("the job slot is no longer reserved for this job")
            handle.started = True
            self._multi = len(spec.runs) > 1
            self._counter.reset()
            self._status = JobStatus(
                state=STARTING, kind=spec.kind, project=spec.project, mode=spec.mode, scene=spec.scene, total=spec.total,
                run=handle.run,
            )
            self._thread = threading.Thread(target=run_job, args=(self, handle, spec), daemon=True)
            self._thread.start()

    def valid(self, handle: SlotHandle) -> bool:
        """True while `handle` could still start: reserved here, not started, released, cancelled or closed."""
        with self._cond:
            return handle is self._handle and not (handle.started or handle.released or handle.refused or self._closed)

    def release(self, handle: SlotHandle) -> None:
        """Give back a reservation that was never started; idempotent, and a no-op once `start` consumed it."""
        with self._cond:
            if handle is not self._handle or handle.started or handle.released:
                return
            handle.released = True
            self._handle = None
            self._status = self._before_reserve
            self._cond.notify_all()

    def current(self) -> JobStatus:
        with self._cond:
            status = self._status
            if status.state in _LIVE and self._handle is not None and self._handle.started:
                done = self._runs_completed if self._multi else self._counter.value()
                return replace(status, scenes_done=done)
            return status

    def cancel(self) -> None:
        """Stop whatever job holds the slot; internal (tests, shutdown). The route uses `cancel_run`."""
        with self._cond:
            self._cancel_locked()

    def cancel_run(self, run: str) -> str:
        """Stop the job only if it is run `run`, comparing and cancelling under one lock: STOPPED, STALE or NOTHING."""
        with self._cond:
            if self._handle is None:
                return NOTHING
            if self._handle.run != run:
                return STALE
            self._cancel_locked()
            return STOPPED

    def lookup(self, run: str) -> RunLookup | None:
        """The live status of run `run`, else its retained final (with its own failure), else None."""
        with self._cond:
            if self._status.run == run and self._handle is not None:
                return RunLookup(self.current(), None)
            return self._retained.get(run)

    def _cancel_locked(self) -> None:
        handle = self._handle
        if handle is None:
            return
        if not handle.started:
            handle.refused = True
            self._status = replace(self._status, state=CANCELLING)
            return
        if self._cancel or self._hooks:
            return
        self._cancel = True
        self._status = replace(self._status, state=CANCELLING)
        if self._child is not None:
            stopper = threading.Thread(target=stop_process_group, args=(self._child, self._kill_delay), daemon=True)
            self._stoppers.append(stopper)
            stopper.start()

    def shutdown(self) -> None:
        """Close the slot, stop the job, and wait (within the bound) for every holder to let go."""
        deadline = time.monotonic() + self._bound
        with self._cond:
            self._closed = True
            self._cancel_locked()
            while self._handle is not None or self._admissions:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                self._cond.wait(remaining)
            thread = self._thread
        if thread is not None:
            thread.join(max(0.0, deadline - time.monotonic()))

    def job_active(self) -> bool:
        with self._cond:
            return self._handle is not None

    def busy_reason(self) -> str | None:
        with self._cond:
            if self._closed:
                return "stopping"
            if self._handle is not None:
                return self._handle.kind
            return "download" if self._admissions else None

    def note_scene_done(self) -> None:
        self._counter.note()

    def scenes_done(self) -> int:
        return self._counter.value()

    def admit_zip(self) -> ZipAdmission | None:
        with self._cond:
            if self._closed or self._handle is not None:
                return None
            self._admissions += 1
            return ZipAdmission()

    def release_zip(self, admission: ZipAdmission) -> None:
        with self._cond:
            if admission.released:
                return
            admission.released = True
            self._admissions -= 1
            self._cond.notify_all()

    def stdout(self) -> StdoutCapture:
        """The bounded stdout of the last finished run."""
        with self._cond:
            return self._stdout

    # The job thread's side (see run_job): none of these is part of the owner's API.

    def begin_run(self, argv: Sequence[str]) -> RunningChild | None:
        with self._cond:
            if self._cancel:
                return None
            prefix = self._prefix if self._prefix is not None else cli_argv_prefix()
            self._child = spawn_run([*prefix, *argv], cwd=self._cwd, env=self._env)
            if self._status.state == STARTING:
                self._status = replace(self._status, state=RUNNING)
            return self._child

    def end_run(self, captured: StdoutCapture) -> None:
        with self._cond:
            self._child = None
            self._stdout = captured

    def cancel_requested(self) -> bool:
        with self._cond:
            return self._cancel

    def note_run_completed(self, count: int) -> None:
        with self._cond:
            self._runs_completed = count

    def enter_hooks(self) -> None:
        with self._cond:
            self._hooks = True

    def final_scenes_done(self, runs: int, completed: int) -> int:
        """Completed runs for a multi-run job, the observed scene counter for a single run."""
        return completed if runs > 1 else self._counter.value()

    def join_stoppers(self) -> None:
        with self._cond:
            stoppers = list(self._stoppers)
            self._stoppers.clear()
        for stopper in stoppers:
            stopper.join()

    def finish(self, handle: SlotHandle, final: JobStatus, failure: dict[str, object] | None = None) -> None:
        """Publish `final` (stamped with the handle's run), keep it with `failure` (that run's own), free the slot."""
        final = replace(final, run=handle.run)
        with self._cond:
            self._retained.put(handle.run, final, failure)
            self._status = final
            self._handle = None
            self._cond.notify_all()
