from collections.abc import Mapping, Sequence

from .known_kind import known_kind
from .plain_int import plain_int
from .progress_vocabulary import FIXED_FAILURE
from .run_hooks import HOOK_FAILURE
from .run_runs import RUN_FAILURE, SPAWN_FAILURE


def failure_from_events(
    events: Sequence[Mapping[str, object]], *, outcome: str, message: str | None
) -> dict[str, object] | None:
    """What a failed job shows: `{kind, message, scene, status}`, or None for any other outcome.

    `message` is the runner's own failure text. The runner's generic text for a non-zero exit gives way to the
    last `fail` event (kind from the six, else `other`); with no `fail` event the kind is `other`. The runner's internal texts become the fixed message. Any other text
    (an approved text a hook chose) stays, as kind `other`. Only `invalid_input` carries a child message.
    """
    if outcome != "failed":
        return None
    if message in (HOOK_FAILURE, SPAWN_FAILURE):  # the runner's own words are not for the user
        return {"kind": "other", "message": FIXED_FAILURE, "scene": None, "status": None}
    if message is not None and message != RUN_FAILURE:
        return {"kind": "other", "message": message, "scene": None, "status": None}
    last = next((event for event in reversed(events) if event.get("type") == "fail"), None)
    if last is None:
        return {"kind": "other", "message": FIXED_FAILURE, "scene": None, "status": None}
    kind = known_kind(last.get("kind"))
    text = last.get("message")
    shown = text if kind == "invalid_input" and isinstance(text, str) and text else FIXED_FAILURE
    return {"kind": kind, "message": shown, "scene": plain_int(last.get("scene")), "status": plain_int(last.get("status"))}
