from dataclasses import dataclass

IDLE = "idle"
STARTING = "starting"
RUNNING = "running"
CANCELLING = "cancelling"
LIVE_STATES = (STARTING, RUNNING, CANCELLING)
FINAL_STATES = ("done", "failed", "cancelled")
STOPPED = "stopped"  # `cancel_run` outcomes: the named run was live and is now stopping,
STALE = "stale"  # another run holds the slot (the named one has ended),
NOTHING = "nothing"  # or nothing holds it


@dataclass(frozen=True)
class JobStatus:
    """What `JobRunner.current()` reports: a state, what the job is, how far it got, and how it ended.

    `state` is one of idle, starting, running, cancelling (live) or done, failed, cancelled (final, published only
    once the hooks have finished and the slot is released). `failure` is plain words and `failure_kind` a short
    machine word; both are None unless the job failed. `notice` is a plain-words string that never changes the outcome.
    """

    state: str = IDLE
    kind: str | None = None
    project: str | None = None
    mode: str | None = None
    scene: int | None = None
    scenes_done: int = 0
    total: int = 0
    failure_kind: str | None = None
    failure: str | None = None
    notice: str | None = None
    run: str | None = None  # the id of the run this status belongs to (uuid4 hex): an identity, not a secret
